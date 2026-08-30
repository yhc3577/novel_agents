"""输出契约 · 后校验 · 统一错误封装（详细设计 §5.1）。

铁律：所有 LLM 返回的 JSON 一律后校验，禁止直接信任。
错误统一封装为「错误类型 + 原因 + 出错片段 + 期望格式」，回喂给模型修正。
"""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Type

from pydantic import BaseModel, ValidationError


class JSONParseError(Exception):
    def __init__(self, reason: str, snippet: str):
        self.reason = reason
        self.snippet = snippet
        super().__init__(reason)


class SchemaValidationError(Exception):
    def __init__(self, reason: str, snippet: str):
        self.reason = reason
        self.snippet = snippet
        super().__init__(reason)


class OutputValidationFailed(Exception):
    """契约校验重试耗尽。"""

    def __init__(self, feedback: list[str]):
        self.feedback = feedback
        super().__init__("\n".join(feedback))


TIER_ORDER = ["low", "mid", "high"]


def escalate(tier: str) -> str:
    """失败升档 low→mid→high。"""
    if tier in TIER_ORDER:
        idx = TIER_ORDER.index(tier)
        if idx < len(TIER_ORDER) - 1:
            return TIER_ORDER[idx + 1]
    return tier


@dataclass
class OutputContract:
    schema: Type[BaseModel]
    max_retries: int = 2
    tier_escalate: bool = True
    extractor: Callable[[str], str | None] | None = None  # 从 markdown 提取 JSON 块（容错解析）
    expected: str = field(default="")  # 期望格式描述，默认从 schema 推导


def _expected_format(schema: Type[BaseModel]) -> str:
    try:
        props = schema.model_json_schema().get("properties", {})
        parts = []
        for name, spec in props.items():
            if "$ref" in spec:
                t = spec["$ref"].split("/")[-1]
            else:
                t = spec.get("type", "?")
                if isinstance(t, list):
                    t = " | ".join(t)
            required = "required" if name in schema.model_json_schema().get("required", []) else "optional"
            parts.append(f"{name}: {t} ({required})")
        return "{" + ", ".join(parts) + "}"
    except Exception:
        return "<schema>"


def _balanced_json(text: str) -> str | None:
    """找第一个完整平衡的 {...} 块。"""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_json_strict(text: str, extractor: Callable[[str], str | None] | None = None) -> dict:
    """容错解析 LLM 输出的 JSON。成功返回 dict；失败抛 JSONParseError（带出错片段）。"""
    candidates = []
    if extractor:
        extracted = extractor(text)
        if extracted:
            candidates.append(extracted)
    candidates.append(text)
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        candidates.append(fence.group(1))
    block = _balanced_json(text)
    if block:
        candidates.append(block)

    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    raise JSONParseError("未能从输出中解析出 JSON 对象", text[:200])


def format_feedback(attempt: int, max_retries: int, err: Exception, contract: OutputContract) -> str:
    """统一错误反馈格式（§5.1），追加到可变尾部段。"""
    expected = contract.expected or _expected_format(contract.schema)
    if isinstance(err, JSONParseError):
        etype, reason = "JSONParseError", err.reason
    elif isinstance(err, ValidationError):
        etype, reason = "SchemaValidationError", err.errors()[0].get("msg", str(err.errors())) if err.errors() else str(err)
    else:
        etype, reason = type(err).__name__, str(err)
    snippet = getattr(err, "snippet", "") or ""
    return (
        f"[输出校验失败 · 第 {attempt + 1}/{max_retries + 1} 次]\n"
        f"错误类型: {etype}\n"
        f"原因: {reason}\n"
        f"出错片段: {snippet[:200]}\n"
        f"期望格式: {expected}\n"
        "请修正后重新输出完整 JSON，不要附加解释。"
    )

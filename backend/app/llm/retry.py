"""反馈式重试引擎（详细设计 §5.1 / §5.2 规则 4）。

generate_checked：LLM 输出 → 容错解析 → Pydantic 后校验；失败时把「错误类型+原因+
出错片段+期望格式」封装成 [纠错反馈] 追加到 prompt **尾部**（可变段），段 1-4 前缀不动，
从而不破坏厂商前缀缓存。失败可升档重试。
"""

from pydantic import BaseModel, ValidationError

from app.llm.contracts import (
    JSONParseError,
    OutputContract,
    OutputValidationFailed,
    escalate,
    format_feedback,
    parse_json_strict,
)
from app.llm.factory import ModelFactory, ModelUnavailable


def append_feedback(prompt: str, feedback: list[str]) -> str:
    """纠错反馈只追加在尾部；prompt 前缀（稳定段 1-4）必须逐字节不变。"""
    return prompt + "\n\n[纠错反馈]\n" + "\n".join(feedback)


async def generate_checked(
    factory: ModelFactory,
    tier: str,
    prompt: str,
    contract: OutputContract,
    *,
    task_type: str,
) -> BaseModel:
    feedback: list[str] = []
    current_tier = tier
    for attempt in range(contract.max_retries + 1):
        try:
            text = await factory.invoke_with_retry(current_tier, [("human", prompt)], task_type=task_type)
            data = parse_json_strict(text, contract.extractor)
            return contract.schema.model_validate(data)
        except (JSONParseError, ValidationError, ModelUnavailable) as e:
            feedback.append(format_feedback(attempt, contract.max_retries, e, contract))
            prompt = append_feedback(prompt, feedback)
            if contract.tier_escalate:
                current_tier = escalate(current_tier)
    raise OutputValidationFailed(feedback)

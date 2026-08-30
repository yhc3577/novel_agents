"""ModelFactory：tier 路由 + API 级重试/跨 provider 降级 + 用量记录（详细设计 §5）。

分工铁律：
- API 级错误（限流/超时/5xx/无 key）→ 本模块指数退避 + 同 tier 跨 provider 降级，**不改 prompt**。
- 内容级错误（JSON 解析/schema 校验）→ retry.generate_checked，**追加纠错反馈**。
"""

import asyncio
import time
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageLog, UserSetting
from app.llm.providers import ProviderConfig, load_providers


class ModelUnavailable(Exception):
    """该 tier 所有 provider 均不可用（无 key / 网络 / 5xx）。"""


def _backoff(attempt: int) -> float:
    return min(2**attempt, 8)  # 1s, 2s, 4s, 8s


def _extract_usage(msg) -> dict:
    """从 AIMessage 提取 usage，兼容各家字段（openai 风格 cached_tokens / moonshot prompt_cache_hit_tokens）。"""
    meta = (msg.response_metadata or {}).get("usage") or {}
    details = meta.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens") or meta.get("prompt_cache_hit_tokens") or 0
    return {
        "prompt_tokens": meta.get("prompt_tokens") or 0,
        "completion_tokens": meta.get("completion_tokens") or 0,
        "cached_tokens": cached,
    }


class ModelFactory:
    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self._providers: list[ProviderConfig] | None = None

    async def _load(self) -> list[ProviderConfig]:
        if self._providers is None:
            self._providers = await load_providers(self.db)
        return [p for p in self._providers if p.enabled]

    async def _user_tier_override(self, tier: str) -> tuple[str, str] | None:
        """用户设置覆盖：user_settings.tier_{tier} = "provider:model"。"""
        settings = await self.db.scalar(select(UserSetting).where(UserSetting.user_id == self.user_id))
        if settings is None:
            return None
        spec = getattr(settings, f"tier_{tier}", None)
        if not spec or ":" not in spec:
            return None
        provider, model = spec.split(":", 1)
        return provider.strip(), model.strip()

    async def available(self, tier: str) -> bool:
        """该 tier 是否有已配置 key 的候选模型（无 key 时图节点走确定性兜底）。"""
        try:
            await self._candidates(tier)
            return True
        except ModelUnavailable:
            return False

    async def _candidates(self, tier: str) -> list[tuple[ProviderConfig, str]]:
        """该 tier 的候选 (provider, model)，按 priority 升序。"""
        providers = await self._load()
        override = await self._user_tier_override(tier)
        result: list[tuple[ProviderConfig, str]] = []
        if override:
            pname, model = override
            for p in providers:
                if p.name == pname and p.api_key:
                    result.append((p, model))
        if not result:
            for p in providers:
                if p.api_key:
                    model = p.resolve_model(tier)
                    if model:
                        result.append((p, model))
        if not result:
            names = ", ".join(p.name for p in providers)
            raise ModelUnavailable(f"无可用模型：该 tier='{tier}' 无已配置 api_key 的 provider（当前: {names}）")
        return result

    def _client(self, pconf: ProviderConfig, model: str):
        # 懒导入：避免无 langchain 环境下测试收集失败；真正调用时才需要
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            base_url=pconf.base_url,
            api_key=pconf.api_key,
            model=model,
            timeout=120,
            max_retries=0,  # 重试由本模块统一控制
            temperature=0.7,
        )

    async def _invoke_once(self, pconf: ProviderConfig, model: str, messages, task_type: str) -> str:
        chat = self._client(pconf, model)
        started = time.monotonic()
        try:
            msg = await chat.ainvoke(messages)
        except Exception as e:  # noqa: BLE001 网络/限流/5xx 一律归为 API 级错误
            raise ModelUnavailable(f"[{pconf.name}/{model}] {type(e).__name__}: {str(e)[:200]}") from e
        usage = _extract_usage(msg)
        await self._record_usage(pconf.name, model, task_type, usage, int((time.monotonic() - started) * 1000))
        return msg.content or ""

    async def _record_usage(self, provider: str, model: str, task_type: str, usage: dict, latency_ms: int) -> None:
        self.db.add(
            UsageLog(
                owner_id=self.user_id,
                provider=provider,
                model=model,
                task_type=task_type,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                cached_tokens=usage["cached_tokens"],
                latency_ms=latency_ms,
            )
        )
        await self.db.flush()

    async def probe(self, provider: str, model: str, prompt: str = "ping") -> tuple[bool, int, str | None]:
        """连通性测试（设置页用）：单次最小调用，不做用量记录。返回 (ok, latency_ms, error)。"""
        providers = await self._load()
        pconf = next((p for p in providers if p.name == provider and p.api_key), None)
        if pconf is None:
            return False, 0, f"provider '{provider}' 未配置 api_key"
        chat = self._client(pconf, model)
        started = time.monotonic()
        try:
            await chat.ainvoke([("human", prompt)])
        except Exception as e:  # noqa: BLE001 网络/鉴权错误都算失败
            return False, int((time.monotonic() - started) * 1000), f"{type(e).__name__}: {str(e)[:200]}"
        return True, int((time.monotonic() - started) * 1000), None

    async def invoke_with_retry(self, tier: str, messages, *, task_type: str, max_retries: int = 2) -> str:
        """API 级重试：指数退避 + 同 tier 跨 provider 降级；prompt 保持不变。"""
        candidates = await self._candidates(tier)
        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            for pconf, model in candidates:
                try:
                    return await self._invoke_once(pconf, model, messages, task_type)
                except ModelUnavailable as e:
                    last_err = e
                    continue
            if attempt < max_retries:
                await asyncio.sleep(_backoff(attempt))
        raise ModelUnavailable(f"tier='{tier}' 重试 {max_retries} 轮后仍失败: {last_err}")

    async def stream(self, tier: str, messages, *, task_type: str) -> AsyncIterator[str]:
        """异步流式；返回 token 增量生成器。调用方负责消费完毕。"""
        candidates = await self._candidates(tier)
        pconf, model = candidates[0]
        chat = self._client(pconf, model)
        started = time.monotonic()
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
        collected = []
        async for chunk in chat.astream(messages):
            piece = chunk.content if isinstance(chunk.content, str) else ""
            if piece:
                collected.append(piece)
                yield piece
        # 流结束后记录用量（部分供应商流响应带 usage；缺失时按内容估算）
        usage["completion_tokens"] = _approx_tokens("".join(collected))
        await self._record_usage(pconf.name, model, task_type, usage, int((time.monotonic() - started) * 1000))


def _approx_tokens(text: str) -> int:
    """粗略估算 token 数（无 usage 时的兜底统计）：中英混合 ~1 token/字符近似。"""
    return max(1, (len(text) + 1) // 2)

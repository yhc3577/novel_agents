"""LLM 成本估算（D10：US-27）。

按 provider 的价格表（元 / 百万 token）估算单次调用成本；缓存命中 token 不参与计费。
价格仅为量级示意，供用量页展示趋势，不作为计费依据。
"""

from decimal import Decimal

# provider -> (prompt 元/百万, completion 元/百万)
PRICING: dict[str, tuple[float, float]] = {
    "deepseek": (1.0, 2.0),
    "qwen": (0.5, 1.5),
    "zhipu": (0.5, 1.5),
    "moonshot": (4.0, 12.0),
    "doubao": (0.3, 0.9),
    "minimax": (1.0, 2.0),
}
DEFAULT_PRICE: tuple[float, float] = (1.0, 2.0)


def estimate_cost(provider: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> Decimal:
    p, c = PRICING.get(provider, DEFAULT_PRICE)
    billable_prompt = max(0, prompt_tokens - cached_tokens)
    cost = (Decimal(billable_prompt) * Decimal(str(p)) + Decimal(completion_tokens) * Decimal(str(c))) / Decimal("1000000")
    return cost.quantize(Decimal("0.000001"))

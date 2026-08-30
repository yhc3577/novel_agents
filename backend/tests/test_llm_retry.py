"""输出契约 · 后校验 · 反馈式重试（US-06 验收）。

验收点：坏 JSON → 契约校验失败 → 错误封装回喂 → 模型修正成功。
不依赖真实网络：用 StubFactory 模拟模型行为。
"""

from pydantic import BaseModel, Field

from app.llm.contracts import JSONParseError, OutputContract, OutputValidationFailed, parse_json_strict
from app.llm.retry import generate_checked


class Sentence(BaseModel):
    sentence: str = Field(min_length=1)
    emotion: str = Field(min_length=1)


class StubFactory:
    """按调用顺序吐出预设响应的模型桩。"""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[str, list]] = []

    async def invoke_with_retry(self, tier: str, messages, *, task_type: str) -> str:
        self.calls.append((tier, messages))
        return self.responses.pop(0)


def test_parse_json_strict_tolerates_fence_and_prose():
    assert parse_json_strict('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_strict('好的，结果如下：\n{"b": 2} 完') == {"b": 2}
    try:
        parse_json_strict("没有任何 JSON")
        raise AssertionError("应当抛 JSONParseError")
    except JSONParseError:
        pass


async def test_bad_json_feedback_retry_then_success():
    contract = OutputContract(schema=Sentence, max_retries=2)
    stub = StubFactory(["这不是 JSON", '{"sentence": "穿过云层，他站在悬崖边。", "emotion": "震撼"}'])
    result = await generate_checked(stub, "low", "任务：写一句话", contract, task_type="test")

    assert isinstance(result, Sentence)
    assert result.sentence.startswith("穿过")
    # 第一次失败后，prompt 尾部被追加了统一封装的纠错反馈
    first_prompt = stub.calls[0][1][0][1]
    second_prompt = stub.calls[1][1][0][1]
    assert "纠错反馈" not in first_prompt
    assert "错误类型: JSONParseError" in second_prompt
    assert "期望格式:" in second_prompt
    assert second_prompt.startswith(first_prompt)  # 前缀逐字节不变，仅追加尾部


async def test_schema_feedback_then_escalate_and_success():
    contract = OutputContract(schema=Sentence, max_retries=3, tier_escalate=True)
    # 第一次缺字段（校验失败），第二次才正确；档位应从 low 升到 mid
    stub = StubFactory(['{"sentence": "只有一句"}', '{"sentence": "x", "emotion": "y"}'])
    result = await generate_checked(stub, "low", "任务", contract, task_type="test")
    assert isinstance(result, Sentence)
    tiers = [c[0] for c in stub.calls]
    assert tiers[0] == "low"
    assert tiers[1] == "mid"
    assert "错误类型: SchemaValidationError" in stub.calls[1][1][0][1]


async def test_all_failures_raise_output_validation_failed():
    contract = OutputContract(schema=Sentence, max_retries=1)
    stub = StubFactory(["坏1", "坏2"])
    try:
        await generate_checked(stub, "low", "任务", contract, task_type="test")
        raise AssertionError("应当抛 OutputValidationFailed")
    except OutputValidationFailed as e:
        assert len(e.feedback) == 2

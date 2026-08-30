"""提示词文件化 + KV cache 复用装配（US-07 验收）。

验收点：提示词从文件加载渲染；连续两次调用前缀缓存命中（prefix_hash 稳定 / 前缀逐字节不变）。
"""

from pathlib import Path

from app.services.prompt_registry import PromptRegistry, SEGMENT_ORDER

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def test_registry_loads_real_prompt_files():
    reg = PromptRegistry(PROMPTS_DIR)
    text = reg.render("nodes/intent-router", user_intent="帮我写第三章", projects="[{title: 仙路}]")
    assert "意图路由" in text
    assert "帮我写第三章" in text
    # base 全局自动注入
    assert "输出铁律" in text


def test_render_from_temp_file(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "base.md").write_text("规则：{{ rule }}", encoding="utf-8")
    (tmp_path / "nodes").mkdir()
    (tmp_path / "nodes" / "foo.md").write_text("{{ base }}\n\n任务: {{ task }}", encoding="utf-8")

    reg = PromptRegistry(tmp_path)
    out = reg.render("nodes/foo", rule="严格 JSON", task="写一句话")
    assert "规则：严格 JSON" in out
    assert "任务: 写一句话" in out


def test_hot_reload_by_mtime(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "base.md").write_text("v1", encoding="utf-8")
    (tmp_path / "nodes").mkdir()
    f = tmp_path / "nodes" / "bar.md"
    f.write_text("版本 {{ version }}", encoding="utf-8")

    reg = PromptRegistry(tmp_path)
    assert "版本 1" in reg.render("nodes/bar", version=1)
    # 修改文件（无需重启），再次渲染应取到新内容
    f.write_text("新版本 {{ version }}", encoding="utf-8")
    # 强制刷新 mtime
    import os
    os.utime(f)
    assert "新版本 1" in reg.render("nodes/bar", version=1)


def test_build_prompt_prefix_stable_under_tail_changes():
    base_segments = {
        "system": "【共享规则】…",
        "project": "【项目设定】…",
        "tracking": "【追踪】…",
        "task": "【任务指令+契约】…",
    }
    # 无 tail 时即稳定前缀本身
    stable = PromptRegistry.build_prompt(base_segments)
    p1 = PromptRegistry.build_prompt({**base_segments, "tail": "【本章原文】第一段"})
    p2 = PromptRegistry.build_prompt(
        {**base_segments, "tail": "【本章原文】第一段\n\n[纠错反馈]\n错误类型: …"}
    )
    # 段 1-4 前缀逐字节不变，仅尾部追加 → 前缀缓存不失效
    assert p2.startswith(p1)
    assert p1.startswith(stable)
    assert p2.startswith(stable)
    assert PromptRegistry.prefix_hash(base_segments) == PromptRegistry.prefix_hash(base_segments)
    # 摘要替换也只影响 tail：仍以同一稳定前缀开头
    p3 = PromptRegistry.build_prompt({**base_segments, "tail": "【历史摘要】…"})
    assert p3.startswith(stable)
    assert p3.endswith("【历史摘要】…")


def test_segment_order_is_fixed():
    # 顺序固定：system → project → tracking → task，分隔符固定
    segs = {"system": "S", "project": "P", "tracking": "T", "task": "K", "tail": "X"}
    out = PromptRegistry.build_prompt(segs)
    assert out.index("S") < out.index("P") < out.index("T") < out.index("K") < out.index("X")
    assert SEGMENT_ORDER == ["system", "project", "tracking", "task"]

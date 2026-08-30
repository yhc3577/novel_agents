"""提示词文件化 + KV cache 复用装配（详细设计 §5.2 / §6）。

- prompts/*.md 由 Jinja2 渲染；模板变量在文件头部注释声明。
- 热重载：按 mtime 失效，改提示词不用改代码、不用重启。
- build_prompt：段 1-4 稳定前缀 + 段 5 可变尾部，前缀逐字节固定 → 命中厂商前缀缓存。
- prefix_hash：观测键 (provider, model, tier, prefix_hash)，仅观测不改变调用路径。
"""

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template

# 稳定前缀段（任务内不变）：system/base → 项目设定+大纲+题材卡 → 追踪上下文+召回包 → 任务指令+契约
SEGMENT_ORDER = ["system", "project", "tracking", "task"]
SEPARATOR = "\n\n"


class PromptRegistry:
    def __init__(self, prompts_dir: Path | None = None):
        # 缺省：backend/prompts（app/services/prompt_registry.py → 上三级）
        self._dir = Path(prompts_dir) if prompts_dir else Path(__file__).resolve().parent.parent.parent / "prompts"
        self._env = Environment(
            loader=FileSystemLoader(str(self._dir)),
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._templates: dict[str, Template] = {}
        self._mtime: dict[str, float] = {}

    def _template(self, name: str) -> Template:
        """按 mtime 热重载：文件变动后重新加载。"""
        path = self._dir / f"{name}.md"
        mt = path.stat().st_mtime
        if name not in self._templates or mt > self._mtime.get(name, 0):
            self._templates[name] = self._env.get_template(f"{name}.md")
            self._mtime[name] = mt
        return self._templates[name]

    def render(self, name: str, **vars) -> str:
        """渲染指定提示词文件。所有节点模板自动注入 {{ base }}（共享规则，与节点共享变量上下文）。"""
        vars.setdefault("base", self._template("system/base").render(**vars))
        return self._template(name).render(**vars)

    # ---- KV cache 复用装配 ----
    @staticmethod
    def build_prompt(segments: dict[str, str]) -> str:
        """按固定段顺序装配：段 1-4 为稳定前缀，段 5（tail）为可变尾部。

        segments 键：system / project / tracking / task / tail。
        摘要、纠错反馈等变化只允许出现在 tail —— 前缀不变 → 命中前缀缓存。
        """
        prefix = SEPARATOR.join(segments[k] for k in SEGMENT_ORDER if k in segments and segments[k])
        tail = segments.get("tail", "")
        if tail:
            return prefix + SEPARATOR + tail
        return prefix

    @staticmethod
    def prefix_hash(segments: dict[str, str]) -> str:
        """稳定前缀的 sha256（观测键用）。"""
        prefix = SEPARATOR.join(segments[k] for k in SEGMENT_ORDER if k in segments and segments[k])
        return hashlib.sha256(prefix.encode("utf-8")).hexdigest()

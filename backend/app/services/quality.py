"""QualityService（US-10）：质量门禁——AI 句式 / 退化 / 标点 / 禁用词 / 大纲契约。

全部为确定性启发式（正则 + 统计），无 LLM 依赖，门禁对每个提交章节执行。
`fail_on="blocking"`：存在 blocking 级别 findings 时抛 QualityBlockError。
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chapter, ChapterRecord, OutlineChapter

# ---- AI 句式：网文里一眼穿帮的书面腔/套话 ----
AI_PATTERNS: list[tuple[str, str, str]] = [
    (r"不难发现", "ai_pattern", "总结腔：『不难发现』"),
    (r"由此可见", "ai_pattern", "总结腔：『由此可见』"),
    (r"总而言之", "ai_pattern", "总结腔：『总而言之』"),
    (r"值得注意的是", "ai_pattern", "插入腔：『值得注意的是』"),
    (r"与此同时", "ai_pattern", "书面腔：『与此同时』"),
    (r"仿佛[^。，]{1,8}一般", "ai_pattern", "比喻腔：『仿佛…一般』"),
    (r"不约而同地", "ai_pattern", "套路词：『不约而同地』"),
    (r"作为[^，。]{1,10}，", "ai_pattern", "悬置腔：『作为…，』"),
    (r"某种程度上", "ai_pattern", "虚词腔：『某种程度上』"),
    (r"然而[,，]?", "ai_pattern", "转折腔：『然而』"),
    (r"不禁[^。，]{1,6}", "ai_pattern", "高频词：『不禁』"),
]
# 退化：重复/口水
DEGENERATION_PATTERNS: list[tuple[str, str, str]] = [
    (r"（{3,}|。{3,}|……{2,}", "degeneration", "连续标点刷字数"),
    (r"(略作停顿|沉默半晌|沉吟片刻)", "degeneration", "动作套话高频"),
]
# 标点问题
PUNCTUATION_PATTERNS: list[tuple[str, str, str]] = [
    (r"[,\.;:?!]{2,}", "punctuation", "半角标点连排"),
    (r"“”[^”]*“”", "punctuation", "引号嵌套错误"),
    (r"！！！|？？？|……！", "punctuation", "情绪标点堆叠"),
]
# 平台禁用词（默认空表，可在 DB 扩展；这里给基础示例）
BANNED_WORDS = ["剽窃", "刷票", "推广", "加微信", "V信", "私信我"]


class QualityBlockError(Exception):
    """门禁未过：存在 blocking findings。"""


@dataclass
class Finding:
    level: str  # blocking / warning
    type: str
    quote: str
    reason: str


@dataclass
class QualityReport:
    findings: list = field(default_factory=list)

    @property
    def blocking(self) -> list:
        return [f for f in self.findings if f.level == "blocking"]


def _scan(text: str, patterns: list) -> list[Finding]:
    out = []
    for regex, kind, reason in patterns:
        for m in re.finditer(regex, text):
            out.append(Finding(level="blocking", type=kind, quote=m.group(0), reason=reason))
    return out


class QualityService:
    def __init__(self, db: Session):
        self.db = db

    def _chapter(self, chapter_id: int) -> Chapter:
        return self.db.get(Chapter, chapter_id)

    async def ai_patterns(self, chapter_id: int, fail_on: str = "blocking") -> list[Finding]:
        ch = await self._chapter(chapter_id)
        findings = _scan(ch.content or "", AI_PATTERNS)
        return self._gate(chapter_id, findings, fail_on)

    async def degeneration(self, chapter_id: int) -> list[Finding]:
        ch = await self._chapter(chapter_id)
        return _scan(ch.content or "", DEGENERATION_PATTERNS)

    async def punctuation(self, chapter_id: int, check: bool = True) -> list[Finding]:
        if not check:
            return []
        ch = await self._chapter(chapter_id)
        return _scan(ch.content or "", PUNCTUATION_PATTERNS)

    async def banned_words(self, chapter_id: int) -> list[dict]:
        ch = await self._chapter(chapter_id)
        text = ch.content or ""
        return [
            {"word": w, "count": text.count(w)}
            for w in BANNED_WORDS
            if text.count(w) > 0
        ]

    async def full_gate(self, chapter_id: int, fail_on: str = "blocking") -> QualityReport:
        """完整门禁：AI 句式 + 退化 + 标点 + 禁用词。返回报告（fail_on=blocking 时抛 QualityBlockError）。"""
        report = QualityReport()
        report.findings += await self.ai_patterns(chapter_id, fail_on="none")
        report.findings += await self.degeneration(chapter_id)
        report.findings += await self.punctuation(chapter_id)
        for hit in await self.banned_words(chapter_id):
            report.findings.append(
                Finding(level="blocking", type="banned_word", quote=hit["word"], reason="禁用词命中")
            )
        self._gate(chapter_id, report.findings, fail_on)
        return report

    async def outline_contract(self, project_id: int) -> dict:
        """大纲契约：已提交章节须与大细纲对齐（无越级/无空洞/细纲存在）。"""
        errors = []
        rows = (
            await self.db.scalars(
                select(Chapter)
                .where(Chapter.project_id == project_id, Chapter.status == "committed")
                .order_by(Chapter.chapter_no)
            )
        ).all()
        committed_nos = [c.chapter_no for c in rows]
        if committed_nos:
            expected = list(range(1, committed_nos[-1] + 1))
            missing = [n for n in expected if n not in committed_nos]
            if missing:
                errors.append(f"提交章节存在空洞：缺失 {missing}")
        # 大纲章节通过 volume 归属 project
        from app.models import Volume

        vols = await self.db.scalars(select(Volume).where(Volume.project_id == project_id))
        oc = await self.db.scalars(
            select(OutlineChapter).where(OutlineChapter.volume_id.in_([v.id for v in vols]))
        )
        for o in oc:
            if not o.beats:
                errors.append(f"大纲章节 {o.chapter_no} 缺少细纲情节点")
        return {"valid": len(errors) == 0, "errors": errors}

    # ---- 内部 ----

    def _gate(self, chapter_id: int, findings: list[Finding], fail_on: str) -> list[Finding]:
        if fail_on == "blocking":
            blocking = [f for f in findings if f.level == "blocking"]
            if blocking:
                raise QualityBlockError(
                    f"章节 {chapter_id} 未过质量门禁：{blocking[0].type}「{blocking[0].quote}」"
                )
        return findings

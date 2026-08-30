"""WordcountService（US-09）：字数度量与"非对称收口"。

度量口径：中文字符按字 + 英文按单词（`zh_hybrid`），贴合网文平台统计习惯。
收口规则（非对称）：下限严格（target×0.95）、上限宽松（target×1.2）——
短篇是网文的主要风险（付费章节字数不足），超长允许一定冗余。
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter

# 中文字符：基本区 + 扩展 A + 全角标点/符号区
_CJK_RE = re.compile(r"[一-鿿㐀-䶿　-〿＀-￯]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")

# 非对称收口系数
LOW_FACTOR = 0.95
HIGH_FACTOR = 1.2


def measure_text(text: str) -> int:
    """统计文本字数：中文按字、英文/数字按词。"""
    if not text:
        return 0
    return len(_CJK_RE.findall(text)) + len(_WORD_RE.findall(text))


class WordcountService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def measure_text(text: str) -> int:
        return measure_text(text)

    async def measure(self, chapter_id: int) -> dict:
        chapter = await self.db.get(Chapter, chapter_id)
        if chapter is None:
            raise LookupError(f"章节 {chapter_id} 不存在")
        return {"metric": "zh_hybrid", "actual": measure_text(chapter.content or "")}

    async def checkpoint(self, chapter_id: int, target: int) -> dict:
        """写中进度：{actual, remaining_user_range}。remaining<0 表示超出目标。"""
        m = await self.measure(chapter_id)
        remaining = target - m["actual"]
        return {"actual": m["actual"], "remaining_user_range": remaining}

    async def evaluate(self, chapter_id: int, target: int) -> str:
        """in_range / under / over（按非对称收口区间判定）。"""
        m = await self.measure(chapter_id)
        return self.evaluate_actual(m["actual"], target)

    @staticmethod
    def evaluate_actual(actual: int, target: int) -> str:
        if actual < target * LOW_FACTOR:
            return "under"
        if actual > target * HIGH_FACTOR:
            return "over"
        return "in_range"

    @staticmethod
    def acceptable_range(target: int) -> tuple[int, int]:
        return int(target * LOW_FACTOR), int(target * HIGH_FACTOR)

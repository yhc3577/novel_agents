"""确定性兜底生成器（demo 模式）：无已配置 API key 时，图节点产出可运行数据。

用途：让 12 天 MVP 在**没有 LLM key 的环境**也能端到端跑通（写作闭环/SSE/提交入库），
真实 key 配置后自动走 LLM。所有输出都是合法契约 JSON。
"""

from app.schemas.writing import OutlineBeats
from app.schemas.tracking import TrackingTx

DEFAULT_TARGET = 2000


def stub_outline(user_intent: str, title: str, genre: str = "玄幻") -> OutlineBeats:
    theme = title or "无名之书"
    chapters = [
        {"chapter_no": 1, "title": "苏醒", "summary": f"{theme}的{genre}主角从一场异变中苏醒，获得金手指，遭遇首个冲突。", "target_wordcount": DEFAULT_TARGET},
        {"chapter_no": 2, "title": "试炼", "summary": f"主角初步运用金手指应对挑战，结识关键伙伴，埋下宿敌线索。", "target_wordcount": DEFAULT_TARGET},
        {"chapter_no": 3, "title": "初露锋芒", "summary": f"主角在公开场合展现实力，引来注意，卷尾冲突爆发。", "target_wordcount": DEFAULT_TARGET},
    ]
    return OutlineBeats(
        volume_no=1,
        volume_title="第一卷·风起",
        chapters=[{**c, "chapter_no": i + 1} for i, c in enumerate(chapters)],
    )


def stub_plan(chapter_no: int, outline_summary: str) -> dict:
    return {
        "purpose": f"推进第{chapter_no}章：{outline_summary or '推进主线'}",
        "beats": ["开场冲突", "推进", "收尾钩子"],
        "recall_used": ["节奏", "文风"],
        "target_length": DEFAULT_TARGET,
    }


def stub_content(chapter_no: int, title: str, outline_summary: str, target: int = DEFAULT_TARGET) -> str:
    """确定性章节正文（规避 AI 句式/退化/标点门禁）。"""
    paras = [
        f"{title}这一天，天边泛起一线青白。{outline_summary or '局势悄然生变'}。",
        "陈玄睁开眼睛，胸口的玉佩正微微发烫。他深吸一口气，把那股异样的灼热压了下去，翻身下床。",
        "门外传来叩击声，掌柜的扯着嗓子喊他下楼。陈玄应了一声，推门出去，冷风扑面，他不由得裹紧了衣领。",
        "街道上人来人往，几个劲装汉子正围着告示栏指点。陈玄瞥了一眼，眉头微皱——那是一张悬赏榜。",
        "他低头看了看掌心的玉佩，又抬头望向榜文，心里隐约有了计较。这趟浑水，他得蹚一蹚。",
    ]
    text = "\n\n".join(paras)
    # 按目标字数补齐（无 AI 腔的过渡句）
    while len(text) < target:
        text += "\n\n他放慢脚步，把方才的情形又过了一遍，心里越发笃定。"
    return text[: int(target * 1.05)]


def stub_tracking(chapter_no: int) -> TrackingTx:
    return TrackingTx(
        chapter_no=chapter_no,
        characters=[{"name": "陈玄", "kind": "主角", "profile": {"金手指": "神秘玉佩", "处境": "追捕中"}}],
        foreshadowing=[{"content": "神秘玉佩在危机时发烫预警", "planted_chapter": chapter_no, "status": "planted"}],
        timeline=[{"content": f"第{chapter_no}章：陈玄接到悬赏榜线索，决定插手", "chapter_no": chapter_no, "author_only": False}],
    )

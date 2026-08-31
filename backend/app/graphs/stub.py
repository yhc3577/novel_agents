"""确定性兜底生成器（demo 模式）：无已配置 API key 时，图节点产出可运行数据。

用途：让 12 天 MVP 在**没有 LLM key 的环境**也能端到端跑通（写作闭环/SSE/提交入库），
真实 key 配置后自动走 LLM。所有输出都是合法契约 JSON。
"""

from app.schemas.writing import BeatsDetail, ChapterBeats, OutlineStructure, OutlineStructureChapter, SettingItem, WorldviewBeats
from app.schemas.tracking import TrackingTx

DEFAULT_TARGET = 2000


def stub_worldview(user_intent: str, title: str, genre: str = "玄幻") -> str:
    """确定性世界观/设定草稿（markdown 段落格式，可被 _parse_worldview 解析入库）。"""
    theme = title or "无名之书"
    return (
        f"## 世界观\n{theme}（{genre}）中灵气复苏，力量体系自成一系，宗门林立、秘境无数。\n"
        f"## 人设\n主角：{user_intent or '陈玄'}，出身平凡却身负神秘玉佩，性格坚韧。\n"
        "## 金手指\n神秘玉佩：危机时发烫预警，可加速修炼、参悟功法。\n"
        "## 势力\n天玄宗：本界顶级宗门，卷末将登场，为主角宿敌线索。\n"
    )


def stub_outline_structure(user_intent: str, title: str, genre: str = "玄幻") -> str:
    """确定性卷/章大纲草稿（格式：卷名：… + 第N章 标题）。"""
    chapters = "\n".join(
        f"第{i + 1}章 {name}" for i, name in enumerate(["苏醒", "试炼", "初露锋芒"])
    )
    return f"卷名：第一卷·风起\n{chapters}"


def stub_chapter_beats() -> str:
    """确定性细纲草稿（格式：每章 摘要：… / 情节点：- …）。"""
    return (
        "第1章 苏醒\n摘要：主角从一场异变中苏醒，获得金手指，遭遇首个冲突。\n情节点：\n"
        "- 天泛青白，主角自废墟中醒来\n- 玉佩发烫预警，金手指觉醒\n\n"
        "第2章 试炼\n摘要：主角初步运用金手指应对挑战，结识关键伙伴，埋下宿敌线索。\n情节点：\n"
        "- 街头遭遇悬赏榜，卷入风波\n- 危急关头玉佩显威\n\n"
        "第3章 初露锋芒\n摘要：主角在公开场合展现实力，引来注意，卷尾冲突爆发。\n情节点：\n"
        "- 出手解围，震慑众人\n- 卷尾强敌压境，悬念收束\n"
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

"""拆文确定性分析（demo 模式）：无 LLM key 时，对原文做真实的文本统计拆解。

这些是"冷启动"分析——从原文直接计算章节边界、情节点摘要、节奏、情绪、文风指标，
LLM key 配置后由对应契约节点产出更深的语义分析。
"""

import re

# 章节标题：第X章/回/节/话/集（行首或换行后）
CHAPTER_RE = re.compile(r"^\s*(?:第\s*[0-9一二三四五六七八九十百千零两]+\s*[章回节话集篇])", re.M)


def split_chapters(text: str) -> list[dict]:
    """按「第X章」切分正文，返回 [{no, title, start, end}]（start/end 为字符偏移）。"""
    if not text:
        return []
    matches = list(CHAPTER_RE.finditer(text))
    if not matches:
        return [{"no": 1, "title": "全书", "start": 0, "end": len(text)}]
    chapters = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title_line = text[start : text.find("\n", start)] if text.find("\n", start) != -1 else text[start : start + 30]
        title = re.sub(r"^\s*", "", title_line)[:30] or "未命名章节"
        chapters.append({"no": i + 1, "title": title, "start": start, "end": end})
    return chapters


def extract_chapter(text: str, chapter_no: int) -> dict:
    """每章提取：摘要 + 情节点 + 情绪 + 钩子（基于确定性规则）。"""
    text = text.strip()
    sentences = re.split(r"[。！？!?]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]
    first = sentences[0][:80] if sentences else text[:80]
    summary = f"第{chapter_no}章概要：{first}…（本段共 {len(text)} 字）"
    beats = [s[:60] for s in sentences[1:4]] or [f"推进第{chapter_no}章情节"]
    emotion = _emotion_tag(text)
    hooks = [s for s in sentences[-3:] if ("？" in s or "？" in s or "!" in s)] or [f"章末留钩：{sentences[-1][:40] if sentences else ''}"]
    return {"chapter_no": chapter_no, "summary": summary, "beats": beats, "mood": emotion, "hooks": hooks[:3]}


_EMOTIONS = {"喜": ["笑", "高兴", "开心", "喜悦", "欢"], "怒": ["怒", "恨", "咬牙", "厉声道", "大怒"], "悲": ["哭", "落泪", "悲", "伤", "叹"], "惊": ["惊", "怔", "震撼", "瞪大", "没想到"]}


def _emotion_tag(text: str) -> str:
    counts = {k: sum(text.count(w) for w in words) for k, words in _EMOTIONS.items()}
    if not any(counts.values()):
        return "平稳"
    return max(counts, key=counts.get)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[。！？!?]", text) if s.strip()]


def aggregate_plot(text: str) -> str:
    sents = _sentences(text)
    return "主线线索：\n- " + "\n- ".join(s[:60] for s in sents[:6])


def aggregate_rhythm(text: str) -> str:
    sents = _sentences(text)
    lens = [len(s) for s in sents]
    avg = sum(lens) / len(lens) if lens else 0
    short = sum(1 for l in lens if l <= 12)
    long_ = sum(1 for l in lens if l >= 40)
    return f"节奏画像：平均句长 {avg:.0f} 字；短句占比 {short * 100 // max(len(lens), 1)}%，长句占比 {long_ * 100 // max(len(lens), 1)}%（短句多=快节奏）"


def aggregate_emotion(text: str) -> str:
    tags = {}
    for k, words in _EMOTIONS.items():
        tags[k] = sum(text.count(w) for w in words)
    return "情绪分布：" + "；".join(f"{k} {tags[k]}" for k in tags if tags[k])


def aggregate_settings(text: str) -> str:
    keywords = ["世界", "大陆", "宗门", "秘境", "城", "王朝", "遗迹", "规则", "法宝", "功法"]
    hits = {k: text.count(k) for k in keywords if text.count(k)}
    return "世界观关键词：\n- " + "\n- ".join(f"{k}（{v} 次）" for k, v in sorted(hits.items(), key=lambda x: -x[1]))


def aggregate_characters(text: str) -> str:
    # 简单命名实体：高频「X道/说/想/喝道」前的主语双字词
    names = re.findall(r"([一-鿿]{2,3})(?:道|说|喝道|问道|笑道|沉声道|想)", text)
    from collections import Counter

    top = Counter(names).most_common(8)
    return "主要角色（按出场频次）：\n- " + "\n- ".join(f"{n}（{c} 次）" for n, c in top) if top else "主要角色：文本中未检测到明显人物"


def aggregate_relations(text: str) -> str:
    names = [n for n, _ in __import__("collections").Counter(re.findall(r"([一-鿿]{2,3})(?:道|说|喝道|问道|笑道|沉声道|想)", text)).most_common(5)]
    pairs = [f"{names[i]} 与 {names[j]}" for i in range(min(2, len(names))) for j in range(i + 1, min(3, len(names)))]
    return "人物关系：\n- " + "\n- ".join(pairs) if pairs else "人物关系：样本不足"


def aggregate_style(text: str) -> str:
    sents = _sentences(text)
    avg = sum(len(s) for s in sents) / max(len(sents), 1)
    dialog = len(re.findall(r"[“「『].+?[”」』]", text))
    return f"文风画像：平均句长 {avg:.0f} 字；对话段落 {dialog} 处；全文 {len(text)} 字。"


def aggregate_golden(text: str) -> str:
    first = text[:600].replace("\n", " ")
    hooks = re.findall(r"[^。！？]*[？!][^。！？]*", first)
    return f"黄金三章评估（前 600 字）：\n开篇：{first[:120]}…\n钩子数：{len(hooks)}\n{aggregate_emotion(first)}"


def aggregate_report(book_title: str, chapters: list, aggregates: dict) -> str:
    lines = [f"《{book_title}》拆文报告", f"章节数：{len(chapters)}", f"总字数：{sum(len(c) for c in chapters)}"]
    for kind in ("plot", "rhythm", "emotion", "settings", "characters", "relations", "style", "golden"):
        if aggregates.get(kind):
            lines.append(f"\n【{kind}】\n{aggregates[kind]}")
    return "\n".join(lines)


# 聚合 kind → 确定性生成器
AGGREGATORS = {
    "plot": aggregate_plot,
    "rhythm": aggregate_rhythm,
    "emotion": aggregate_emotion,
    "settings": aggregate_settings,
    "characters": aggregate_characters,
    "relations": aggregate_relations,
    "style": aggregate_style,
    "golden": aggregate_golden,
}

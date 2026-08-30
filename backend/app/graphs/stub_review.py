"""审查/去味的确定性兜底（demo 模式）：复用 quality 的启发式正则 + 文本统计。

无 LLM key 时：4 个 reviewer 各跑对应维度的正则/统计扫描，产出结构化 findings；
Deslop 做短语级替换 + 标点压缩。全部真实计算，非占位。
"""

import re

from app.services.quality import AI_PATTERNS, DEGENERATION_PATTERNS, PUNCTUATION_PATTERNS

# 4 个审查维度（reviewer 键 → 中文标签）
REVIEWERS = [("plot", "情节逻辑"), ("character", "人物一致性"), ("style", "文风表达"), ("rhythm", "节奏结构")]


def _char_names(text: str) -> list[str]:
    return re.findall(r"([一-鿿]{2,3})(?:道|说|喝道|问道|笑道|沉声道|想|厉声道)", text)


def stub_review(reviewer: str, chapter_text: str, context: str = "") -> list[dict]:
    text = chapter_text or ""
    findings: list[dict] = []

    def push(severity: str, type_: str, quote: str, reason: str, suggestion: str = ""):
        findings.append(
            {"reviewer": reviewer, "severity": severity, "type": type_, "quote": quote, "reason": reason, "suggestion": suggestion}
        )

    if reviewer == "style":
        for regex, kind, reason in AI_PATTERNS:
            for m in re.finditer(regex, text):
                push("warning", kind, m.group(0), reason, "改为口语化表达或直接删除")
            if len(findings) >= 6:
                break
    elif reviewer == "rhythm":
        sents = [s for s in re.split(r"[。！？!?]", text) if len(s.strip()) > 5]
        if sents:
            lens = [len(s) for s in sents]
            avg = sum(lens) / len(lens)
            if max(lens) - min(lens) <= avg * 0.5:
                push("warning", "monotone", sents[0][:20], "句长高度均匀，节奏单调", "穿插短句制造节奏起伏")
            if avg > 40:
                longest = max(sents, key=len)
                push("warning", "long_sentence", longest[:30], "平均句长过长，阅读负担重", "拆分长句，一句一意")
    elif reviewer == "plot":
        for regex, kind, reason in DEGENERATION_PATTERNS:
            for m in re.finditer(regex, text):
                push("blocking", kind, m.group(0), reason, "删除重复内容")
        if not text.strip():
            push("blocking", "empty", "", "正文为空", "补充本章内容")
    elif reviewer == "character":
        names = _char_names(text)
        if not names:
            push("warning", "no_character", text[:20], "未检测到人物行动/对话", "补充人物行动推动情节")
    # 标点：所有维度都检查
    for regex, kind, reason in PUNCTUATION_PATTERNS:
        for m in re.finditer(regex, text):
            push("blocking", kind, m.group(0), reason, "修正标点")
    return findings


def stub_summary(findings: list[dict]) -> tuple[int, str, list[str], str]:
    n_block = sum(1 for f in findings if f["severity"] == "blocking")
    n_warn = len(findings) - n_block
    score = max(0, 100 - n_block * 30 - n_warn * 5)
    if score >= 90:
        verdict = "优秀，可直接发布"
    elif score >= 75:
        verdict = "建议小改后发布"
    elif score >= 60:
        verdict = "需要修改"
    else:
        verdict = "问题较多，建议大改"
    must_fix = [f"{f['type']}「{f['quote'][:20]}」" for f in findings if f["severity"] == "blocking"][:5]
    advice = f"共 {len(findings)} 条 finding（blocking {n_block} / warning {n_warn}）"
    return score, verdict, must_fix, advice


# 去味短语替换表（确定性）
DESLOP_MAP = [
    ("不难发现", "这才看清"),
    ("由此可见", "这样看来"),
    ("总而言之", ""),
    ("值得注意的是", ""),
    ("与此同时", "这时"),
    ("不约而同地", "同时"),
    ("某种程度上", ""),
    ("然而", "可"),
    ("不禁", "忍不住"),
    ("仿佛", "好像"),
    ("略作停顿", ""),
    ("沉默半晌", ""),
    ("沉吟片刻", ""),
]


def stub_deslop(text: str) -> str:
    out = text
    for k, v in DESLOP_MAP:
        out = out.replace(k, v)
    # 压缩连续标点
    out = re.sub(r"(。)\1+", "。", out)
    out = re.sub(r"(，)\1+", "，", out)
    out = re.sub(r"！{2,}", "！", out)
    out = re.sub(r"？{2,}", "？", out)
    out = re.sub(r"……{2,}", "……", out)
    out = re.sub(r"[,\.;:?!]{2,}", lambda m: m.group(0)[0], out)
    out = re.sub(r"[，。！？]+\s*$", "", out).strip()
    return out or text


def grade_findings(findings: list[dict]) -> tuple[str, int, str]:
    n_block = sum(1 for f in findings if f["severity"] == "blocking")
    n_warn = len(findings) - n_block
    score = max(0, 100 - n_block * 30 - n_warn * 5)
    bands = [(90, "A", "优秀，可发布"), (75, "B", "小改后发布"), (60, "C", "需要修改"), (40, "D", "较大修改"), (20, "E", "大幅重写"), (0, "F", "严重问题")]
    for thr, grade, desc in bands:
        if score >= thr:
            return grade, score, desc
    return "G", score, "无法发布"

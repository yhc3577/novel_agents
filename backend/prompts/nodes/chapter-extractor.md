{# 变量约定: base / chapter_text / chapter_no #}
{{ base }}

# 章节拆解（chapter-extractor）

阅读给定的章节正文，提取该章的结构化信息。只依据**本章正文**，不要脑补前文内容。

## 章节正文
{{ chapter_text }}

## 输出契约（严格 JSON）
{
  "chapter_no": {{ chapter_no }},
  "summary": "一章内容概括（80-150 字）",
  "beats": ["情节点1", "情节点2", "情节点3"],
  "mood": "本章情绪基调（如：压抑 / 热血 / 轻松）",
  "hooks": ["章末钩子（悬念/承诺/转折），可为空数组"]
}

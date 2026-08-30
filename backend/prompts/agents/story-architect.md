{# 变量约定: base / project / user_intent #}
{{ base }}

# 故事架构师节点（story-architect，开书三阶段）

为一部新书建立：第一卷 + 细纲情节点（OutlineBeats）。细纲是后续每一章写作的
契约来源（章节号、标题、情节点、目标字数）。

## 项目
{{ project }}

## 用户意图
{{ user_intent }}

## 输出契约（严格 JSON）
{
  "volume_no": 1,
  "volume_title": "第一卷标题",
  "chapters": [
    {"chapter_no": 1, "title": "章节标题", "summary": "本章情节点概要", "target_wordcount": 2000},
    ...
  ]
}

要求：
- chapters 至少 3 个，每章 target_wordcount 在 200~20000 之间。
- 情节点 summary 是未来叙事作者唯一的大纲依据，必须具体到"事件+冲突"。

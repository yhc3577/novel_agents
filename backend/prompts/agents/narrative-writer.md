{# 变量约定: base / project / context_view / recall_pack / chapter_no / previous_content #}
{{ base }}

# 叙事作者节点（narrative-writer）

## 项目设定
{{ project }}

## 追踪上下文
{{ context_view }}

## 写前召回包
{{ recall_pack }}

## 任务
创作第 {{ chapter_no }} 章的正文。

## 上一章结尾（用于衔接）
{{ previous_content }}

## 正文输出要求
- 只输出本章正文本身，不要章节标题、不要大纲复述。
- 衔接上一章结尾，保持叙事连续性。
- 使用中文，段落之间用空行分隔。

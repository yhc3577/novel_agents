{# 变量约定: base / kind / book_title / aggregate_context #}
{{ base }}

# 拆文聚合（analysis-aggregate）

基于给定的整本书拆解素材，产出「{{ kind }}」维度的分析。返回一段可直接阅读的中文分析文本
（markdown 允许，600-1200 字），做到：观点明确、引用原文依据、给出可执行结论。

## 书
{{ book_title }}

## 拆解素材
{{ aggregate_context }}

## 输出契约（严格 JSON）
{
  "analysis": "「{{ kind }}」维度的完整分析文本"
}

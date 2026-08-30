{# 变量约定: base / user_intent / projects #}
{{ base }}

# 意图路由

用户在创作系统里的输入可能是：新建/修改大纲、写一章、审查、拆书、扫榜、查询等。
请把输入归类到以下意图之一：`create_outline` / `write_chapter` / `review_chapter` / `analyze` / `scan` / `query` / `other`。

如果输入隐含某个项目，给出 `project_ref`（项目标题或 slug，否则为 null）。

## 用户输入
{{ user_intent }}

## 可用项目
{{ projects }}

## 输出契约（严格 JSON）
{
  "intent": "枚举值之一",
  "project_ref": "项目标题或 null"
}

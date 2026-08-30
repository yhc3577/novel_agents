{# 变量约定: base / project / user_intent #}
{{ base }}

# 篇幅路由（length-routing）

根据项目设定与用户本次意图，决定这本书的篇幅定位与本次要写的章节数。

## 项目
{{ project }}

## 用户意图
{{ user_intent }}

## 输出契约（严格 JSON）
{
  "book_type": "long 或 short",
  "chapters": 本次要连续创作的章节数（至少 1）
}

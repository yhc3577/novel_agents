{# 变量约定: base / chapter_text / chapter_no #}
{{ base }}

# 追踪提取（tracking-extract）

根据本章正文，提取需要上报到小说世界追踪的事务。只上报**正文里真实出现**的新增或变化，
不要臆造。

## 本章正文
{{ chapter_text }}

## 输出契约（严格 JSON）
{
  "chapter_no": {{ chapter_no }},
  "characters": [
    {"name": "角色名", "kind": "主角/配角/反派/路人", "profile": {"关键词": "值"}, "active_status": "active/deceased/absent"}
  ],
  "foreshadowing": [
    {"content": "伏笔内容", "status": "planted/resolved"}
  ],
  "timeline": [
    {"content": "时间线事件", "author_only": false}
  ]
}

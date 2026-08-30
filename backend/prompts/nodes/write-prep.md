{# 变量约定: base / project / tracking / recall_pack / chapter_no / task #}
{{ base }}

# 写作预备（write_prep）

## 项目设定
{{ project }}

## 追踪上下文
{{ tracking }}

## 写前召回包（情绪模块 / 节奏 / 文风 / 题材卡）
{{ recall_pack }}

## 本章任务
第 {{ chapter_no }} 章：{{ task }}

请输出本章的写作方案（严格 JSON），字段：
{
  "purpose": "本章叙事目的（一段话）",
  "beats": ["情节点 1", "情节点 2"],
  "recall_used": ["用到的召回模块"],
  "target_length": 2000
}

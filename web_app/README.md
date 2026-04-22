# Medical KG QA Studio

这个目录是项目的可视化问答工作台，不参与 `docs/` 中的项目讲解主线。

## 启动

在项目根目录执行：

```bash
.venv/bin/python web_app/server.py
```

默认访问：

```text
http://127.0.0.1:8000
```

## 功能

- 规则匹配 / LLM 通道切换
- 医疗问题问答
- 实体识别结果展示
- `question_type` 或 LLM 查询计划展示
- Cypher 展示
- Neo4j 原始查询结果展示
- 简单图谱子图可视化

## 接口

```text
GET  /api/status
POST /api/rule/chat
POST /api/llm/chat
```

请求格式：

```json
{
  "question": "高血压不能吃什么？"
}
```

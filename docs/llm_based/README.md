# llm_based 课件目录

这个目录用于讲解 LLM 版问答通道，对应代码目录为 `llm_based/`。

LLM 通道保持 Neo4j 图谱内容不变，但不复用规则版的 `question_parser.py` 和 `answer_search.py`，而是独立完成查询规划、Cypher 构造、图谱查询和答案生成。

## 当前代码文件

```text
llm_based/
├── config.py
├── schema.py
├── entity_linker.py
├── llm_client.py
├── intent_planner.py
├── cypher_builder.py
├── graph_client.py
├── answer_generator.py
└── chatbot_graph.py
```

## 建议讲解顺序

1. `llm_based/schema.py`
2. `llm_based/config.py`
3. `llm_based/entity_linker.py`
4. `llm_based/llm_client.py`
5. `llm_based/intent_planner.py`
6. `llm_based/cypher_builder.py`
7. `llm_based/graph_client.py`
8. `llm_based/answer_generator.py`
9. `llm_based/chatbot_graph.py`

## 执行流程

```text
用户问题
  -> entity_linker.py      从 dict/ 中识别并校验实体
  -> intent_planner.py     用 LLM 生成结构化查询计划
  -> cypher_builder.py     根据查询计划生成 Cypher
  -> graph_client.py       查询 Neo4j 图谱
  -> answer_generator.py   用 LLM 基于图谱结果生成回答
  -> chatbot_graph.py      串联完整流程
```

## 查询计划示例

关系查询：

```python
{
    "action": "query_relation",
    "subject": {"name": "高血压", "label": "Disease"},
    "relation": "no_eat",
    "direction": "outgoing"
}
```

属性查询：

```python
{
    "action": "query_property",
    "subject": {"name": "高血压", "label": "Disease"},
    "property": "cause"
}
```

## 和 rule_based 的区别

| 对比项 | rule_based | llm_based |
| --- | --- | --- |
| 问题理解 | 词典 + 手写规则 | 实体对齐 + LLM 查询计划 |
| 查询生成 | 固定 `question_type` 映射 | 查询计划动态生成 Cypher |
| 答案生成 | 模板回答 | 基于图谱结果的 LLM 回答 |
| 图谱内容 | Neo4j | Neo4j |
| 适合场景 | 稳定、可控、便于 debug | 更灵活、适合复杂表达 |

## 启动方式

先在 `llm_based/config.py` 中填写模型配置：

```python
LLM_API_KEY = "你的 API Key"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
LLM_TIMEOUT = 30
```

然后在项目根目录执行：

```bash
python -m llm_based.chatbot_graph
```

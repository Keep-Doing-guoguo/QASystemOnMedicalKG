# llm_based

这个目录是大模型版问答通道，保持 Neo4j 图谱内容不变。

当前职责划分：

```text
用户问题
  -> entity_linker.py      从 dict/ 中识别并校验实体
  -> intent_planner.py     用 LLM 生成结构化查询计划
  -> cypher_builder.py     根据查询计划生成 Cypher
  -> graph_client.py       查询 Neo4j 图谱
  -> answer_generator.py   用 LLM 基于图谱结果生成回答
```

LLM 通道不依赖 `rule_based/question_parser.py` 或 `rule_based/answer_search.py`。它和规则版共享的是 `dict/` 词典和 Neo4j 图谱内容。

## 模型配置

默认使用 OpenAI 兼容的 Chat Completions 接口，不新增 Python 依赖。

直接修改 `llm_based/config.py`：

```python
LLM_API_KEY = "你的 API Key"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_MODEL = "gpt-4o-mini"
LLM_TIMEOUT = 30
```

如果使用其他 OpenAI 兼容服务，只需要修改 `LLM_BASE_URL` 和 `LLM_MODEL`。

## 启动方式

在项目根目录执行：

```bash
python -m llm_based.chatbot_graph
```

退出：

```text
q
quit
exit
```

## 查询计划格式

LLM 会生成新的查询计划，而不是规则版的 `question_types`：

```python
{
    "action": "query_relation",
    "subject": {"name": "高血压", "label": "Disease"},
    "relation": "no_eat",
    "direction": "outgoing"
}
```

属性查询示例：

```python
{
    "action": "query_property",
    "subject": {"name": "高血压", "label": "Disease"},
    "property": "cause"
}
```

## 注意

如果 `llm_based/config.py` 中没有配置 `LLM_API_KEY`，查询规划器不会调用大模型，只会根据实体类型走最弱兜底：

```text
disease -> query_property(desc)
symptom -> query_relation(has_symptom, incoming)
```

这可以保证代码可导入、可调试，但正式使用 LLM 通道时需要配置 API Key。

# rule_based

这个目录保存当前项目的规则匹配版问答链路，后续可以和 LLM 版问答链路并行存在。

当前规则版流程：

```text
用户问题
  -> question_classifier.py  基于词典和规则识别实体、问题类型
  -> question_parser.py      将问题类型转换为 Neo4j Cypher
  -> answer_search.py        查询 Neo4j 并用模板组织答案
```

目录文件：

```text
rule_based/
├── __init__.py
├── question_classifier.py
├── question_parser.py
└── answer_search.py
```

后续如果新增 LLM 分支，建议新建：

```text
llm_based/
├── __init__.py
├── llm_question_classifier.py
├── llm_answer_generator.py
└── README.md
```

这样规则版和 LLM 版可以共享 Neo4j 图谱内容，但保持不同的问题理解和答案生成逻辑。

# rule_based 课件目录

这个目录用于讲解规则匹配版问答链路中的核心 Python 文件，对应代码目录为 `rule_based/`。

当前内容：

- [answer_search.md](./answer_search.md)
- [build_medicalgraph.md](./build_medicalgraph.md)
- [chatbot_graph.md](./chatbot_graph.md)
- [question_classifier.md](./question_classifier.md)
- [question_parser.md](./question_parser.md)

建议讲解顺序：

1. `rule_based/build_medicalgraph.py`
2. `rule_based/question_classifier.py`
3. `rule_based/question_parser.py`
4. `rule_based/answer_search.py`
5. `rule_based/chatbot_graph.py`

这个顺序比较符合系统执行流程：

1. 先构建图谱
2. 再识别问题
3. 再生成查询
4. 最后返回答案
5. 再看主入口如何把完整问答流程串起来

如果要看 LLM 通道，请转到 [docs/llm_based](../llm_based/README.md)。

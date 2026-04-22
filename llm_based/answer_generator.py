try:
    from llm_based.schema import PROPERTY_QUERIES, RELATION_QUERIES
except ModuleNotFoundError:
    from schema import PROPERTY_QUERIES, RELATION_QUERIES


class AnswerGenerator:
    """把图谱查询结果转换成最终回答。

    优先让 LLM 基于 graph_results 生成更自然的回答；如果 LLM 不可用、
    网络失败或返回空内容，则退回到本地模板，保证调试流程不中断。
    """

    def __init__(self, llm_client, num_limit=20):
        self.debug = True
        self.llm_client = llm_client
        # 最多传给 LLM / 模板的结果条数，避免长结果拖慢回答。
        self.num_limit = num_limit

    def generate(self, question, plan, graph_results):
        self.debug_print("question", question)
        self.debug_print("plan", plan)
        self.debug_print("graph_results", graph_results)
        # 图谱没有查到结果时，不让 LLM 自由发挥，直接返回固定兜底。
        if not graph_results:
            self.debug_print("skip_llm_reason", "No graph results.")
            return "当前知识图谱中没有查到相关信息。"

        # 只把图谱结果交给 LLM，让回答事实受 Neo4j 结果约束。
        llm_answer = self.llm_client.chat_text(
            self._system_prompt(),
            {
                "question": question,
                "query_plan": plan,
                "graph_results": graph_results[: self.num_limit],
            },
        )
        self.debug_print("llm_answer", llm_answer)
        if llm_answer:
            return llm_answer
        # LLM 调用失败时使用本地模板，方便离线调试。
        template_answer = self._template_answer(plan, graph_results)
        self.debug_print("template_answer", template_answer)
        return template_answer

    def _template_answer(self, plan, graph_results):
        """LLM 失败时的简易回答模板。"""
        action = plan.get("action")
        subject = plan.get("subject", {}).get("name", "")
        self.debug_print("template_action", action)

        if action == "query_property":
            # 属性查询结果统一放在 value 字段里。
            property_name = plan["property"]
            field_name = PROPERTY_QUERIES[property_name]["name"]
            values = [self._stringify(item.get("value")) for item in graph_results]
            values = self._unique_non_empty(values)
            return "{0}的{1}：{2}".format(subject, field_name, "；".join(values[: self.num_limit]))

        if action == "query_relation":
            # 关系查询结果统一把目标节点名称放在 object 字段里。
            relation = plan["relation"]
            relation_name = RELATION_QUERIES[relation]["name"]
            objects = [item.get("object") for item in graph_results]
            objects = self._unique_non_empty(objects)
            return "{0}相关的{1}包括：{2}".format(subject, relation_name, "；".join(objects[: self.num_limit]))

        return "当前知识图谱中没有查到相关信息。"

    def _stringify(self, value):
        # Neo4j 中部分属性是 list，例如 cure_way，需要先拼成字符串。
        if isinstance(value, list):
            return "；".join(str(item) for item in value if item)
        if value is None:
            return ""
        return str(value)

    def _unique_non_empty(self, values):
        # 去重并过滤空值，同时保持原始顺序。
        result = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result

    def _system_prompt(self):
        # 明确限制 LLM 只能根据 graph_results 回答，降低幻觉风险。
        return """
你是医疗知识图谱问答系统的回答生成器。
你只能根据 graph_results 回答，不能补充图谱外医学知识。
不能给出诊断结论，不能替代医生建议。
如果 graph_results 为空，回答“当前知识图谱中没有查到相关信息。”
回答要简洁、自然，说明信息来自当前知识图谱。
""".strip()

    def debug_print(self, name, value):
        if self.debug:
            print("[AnswerGenerator] {0}: {1}".format(name, value))

try:
    from llm_based.schema import PROPERTY_QUERIES, RELATION_QUERIES
    from llm_based.runtime import get_logger
except ModuleNotFoundError:
    from schema import PROPERTY_QUERIES, RELATION_QUERIES
    from runtime import get_logger


class AnswerGenerator:
    """把图谱查询结果转换成最终回答。

    优先让 LLM 基于 graph_results 生成更自然的回答；如果 LLM 不可用、
    网络失败或返回空内容，则退回到本地模板，保证调试流程不中断。
    """

    def __init__(self, llm_client, num_limit=20):
        self.debug = False
        self.logger = get_logger("answer_generator")
        self.llm_client = llm_client
        # 最多传给 LLM / 模板的结果条数，避免长结果拖慢回答。
        self.num_limit = num_limit

    def generate(self, question, plan, graph_results, history=None):
        self.debug_print("question", question)
        self.debug_print("plan", plan)
        self.debug_print("graph_results", graph_results)
        # 图谱没有查到结果时，不让 LLM 自由发挥，直接返回固定兜底。
        if not graph_results:
            self.debug_print("skip_llm_reason", "No graph results.")
            return "当前知识图谱中没有查到相关信息。"

        if self._should_use_template_only(plan, graph_results):
            template_answer = self._template_answer(plan, graph_results)
            self.debug_print("template_only_answer", template_answer)
            return template_answer

        # 只把图谱结果交给 LLM，让回答事实受 Neo4j 结果约束。
        payload = {
            "question": question,
            "query_plan": plan,
            "graph_results": self._truncate_graph_results(graph_results[: self.num_limit]),
        }
        if history:
            payload["conversation_history"] = self._format_history(history)

        llm_answer = self.llm_client.chat_text(self._system_prompt(), payload)
        self.debug_print("llm_answer", llm_answer)
        if llm_answer:
            return llm_answer
        # LLM 调用失败时使用本地模板，方便离线调试。
        template_answer = self._template_answer(plan, graph_results)
        self.debug_print("template_answer", template_answer)
        return template_answer

    def _should_use_template_only(self, plan, graph_results):
        if plan.get("action") != "query_property":
            return False
        if plan.get("property") not in {"desc", "cause", "prevent"}:
            return False
        first_value = self._stringify(graph_results[0].get("value"))
        return len(first_value) > 240

    def _truncate_graph_results(self, graph_results, value_limit=320):
        truncated = []
        for item in graph_results:
            new_item = dict(item)
            value = new_item.get("value")
            if isinstance(value, str) and len(value) > value_limit:
                new_item["value"] = value[:value_limit] + "..."
            elif isinstance(value, list):
                joined = self._stringify(value)
                if len(joined) > value_limit:
                    new_item["value"] = joined[:value_limit] + "..."
            truncated.append(new_item)
        return truncated

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

        if action == "query_relation_chain":
            objects = [item.get("object") for item in graph_results]
            objects = self._unique_non_empty(objects)
            if not objects:
                return "当前知识图谱中没有查到相关信息。"
            return "{0}经过两跳关系可关联到：{1}".format(subject, "；".join(objects[: self.num_limit]))

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

    @staticmethod
    def _format_history(history):
        lines = []
        for turn in history[-6:]:
            role = turn.get("role")
            if role == "summary":
                lines.append("对话摘要：" + turn.get("content", ""))
            elif role == "user":
                lines.append("用户：" + turn.get("question", ""))
            elif role == "assistant":
                lines.append("助手：" + turn.get("answer", "")[:200])
        return "\n".join(lines)

    def _system_prompt(self):
        # 明确限制 LLM 只能根据 graph_results 回答，降低幻觉风险。
        return """
你是医疗知识图谱问答系统的回答生成器。
你只能根据 graph_results 回答，不能补充图谱外医学知识。
不能给出诊断结论，不能替代医生建议。
如果 graph_results 为空，回答"当前知识图谱中没有查到相关信息。"
回答要简洁、自然，说明信息来自当前知识图谱。

如果提供了 conversation_history，请参考历史对话生成连贯的回答。
例如：如果用户之前问了感冒的症状，当前问的是感冒的用药，回答时可以自然衔接。
""".strip()

    def debug_print(self, name, value):
        if self.debug:
            self.logger.info("%s: %s", name, value)

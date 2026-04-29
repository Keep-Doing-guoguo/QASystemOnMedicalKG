try:
    from llm_based.schema import (
        PROPERTY_QUERIES,
        RELATION_QUERIES,
        SUPPORTED_ACTIONS,
        CHAIN_TEMPLATES,
        schema_for_prompt,
    )
except ModuleNotFoundError:
    from schema import (
        PROPERTY_QUERIES,
        RELATION_QUERIES,
        SUPPORTED_ACTIONS,
        CHAIN_TEMPLATES,
        schema_for_prompt,
    )


class IntentPlanner:
    """把用户问题规划成结构化查询计划。

    LLM 不直接生成 Cypher，而是生成受 schema 约束的 plan；
    后续再由 CypherBuilder 把 plan 转成可执行查询。
    """

    def __init__(self, llm_client):
        self.debug = True
        self.llm_client = llm_client

    def plan(self, question, linked_entities, history=None, memory_context=None):
        self.debug_print("question", question)
        self.debug_print("linked_entities", linked_entities)
        # 没有实体就不让 LLM 规划，避免凭空生成图谱查询。
        if not linked_entities:
            self.debug_print("skip_reason", "No linked entities.")
            return {}

        # 把用户问题、已识别实体和 schema 一起交给 LLM。
        payload = {
            "question": question,
            "linked_entities": linked_entities,
            "schema": schema_for_prompt(),
        }
        if history:
            payload["conversation_history"] = self._format_history(history)
        if memory_context:
            payload["memory_context"] = memory_context

        plan = self.llm_client.chat_json(self._system_prompt(), payload)
        self.debug_print("raw_plan", plan)
        # 所有 LLM 输出都必须过白名单校验。
        normalized_plan = self._normalize_plan(plan)
        self.debug_print("normalized_plan", normalized_plan)
        if normalized_plan:
            return normalized_plan
        # LLM 不可用或输出非法时，使用最小兜底计划，方便调试。
        fallback_plan = self._fallback_plan(linked_entities)
        self.debug_print("fallback_plan", fallback_plan)
        return fallback_plan

    def _normalize_plan(self, plan):
        """校验并规整 LLM 输出，防止非法 action/relation/property 进入查询。"""
        if not isinstance(plan, dict):
            self.debug_print("normalize_reject", "Plan is not a dict.")
            return {}

        action = plan.get("action")
        if action not in SUPPORTED_ACTIONS:
            self.debug_print("normalize_reject", "Unsupported action: {0}".format(action))
            return {}

        subject = plan.get("subject")
        if not isinstance(subject, dict):
            self.debug_print("normalize_reject", "Subject is not a dict.")
            return {}
        if not subject.get("name") or not subject.get("label"):
            self.debug_print("normalize_reject", "Subject name or label is empty.")
            return {}

        if action == "query_property":
            # 属性名必须来自 PROPERTY_QUERIES 白名单。
            if plan.get("property") not in PROPERTY_QUERIES:
                self.debug_print("normalize_reject", "Unsupported property: {0}".format(plan.get("property")))
                return {}
            return {
                "action": action,
                "subject": {
                    "name": subject["name"],
                    "label": subject["label"],
                },
                "property": plan["property"],
            }

        if action == "query_relation_chain":
            template_name = plan.get("chain_template")
            steps = plan.get("steps")
            if template_name not in CHAIN_TEMPLATES:
                self.debug_print("normalize_reject", "Unsupported chain template: {0}".format(template_name))
                return {}
            template = CHAIN_TEMPLATES[template_name]
            if subject.get("label") != template["subject_label"]:
                self.debug_print("normalize_reject", "Chain subject label mismatch.")
                return {}
            if not isinstance(steps, list) or len(steps) != len(template["steps"]):
                self.debug_print("normalize_reject", "Unsupported steps for relation chain.")
                return {}
            normalized_steps = []
            for step, expected in zip(steps, template["steps"]):
                if not isinstance(step, dict):
                    self.debug_print("normalize_reject", "Chain step is not a dict.")
                    return {}
                relation = step.get("relation")
                direction = step.get("direction", "outgoing")
                if relation != expected["relation"] or direction != expected["direction"]:
                    self.debug_print("normalize_reject", "Chain steps do not match template.")
                    return {}
                normalized_steps.append({"relation": relation, "direction": direction})
            return {
                "action": action,
                "subject": {
                    "name": subject["name"],
                    "label": subject["label"],
                },
                "chain_template": template_name,
                "steps": normalized_steps,
            }

        # 关系名和方向必须来自允许范围。
        relation = plan.get("relation")
        direction = plan.get("direction", "outgoing")
        if relation not in RELATION_QUERIES:
            self.debug_print("normalize_reject", "Unsupported relation: {0}".format(relation))
            return {}
        if direction not in {"outgoing", "incoming"}:
            self.debug_print("normalize_reject", "Unsupported direction: {0}".format(direction))
            return {}
        return {
            "action": action,
            "subject": {
                "name": subject["name"],
                "label": subject["label"],
            },
            "relation": relation,
            "direction": direction,
        }

    def _fallback_plan(self, linked_entities):
        """没有 LLM 可用时的最小兜底：疾病查简介，症状反查疾病。"""
        for entity in linked_entities:
            if "Disease" in entity["labels"]:
                return {
                    "action": "query_property",
                    "subject": {"name": entity["name"], "label": "Disease"},
                    "property": "desc",
                }
        for entity in linked_entities:
            if "Symptom" in entity["labels"]:
                return {
                    "action": "query_relation",
                    "subject": {"name": entity["name"], "label": "Symptom"},
                    "relation": "has_symptom",
                    "direction": "incoming",
                }
        return {}

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
        # 提示词明确要求只输出 JSON 查询计划，不回答医学问题。
        return """
你是医疗知识图谱问答系统的查询规划器，只输出 JSON，不回答医学问题。

你需要根据用户问题、已识别实体和图谱 schema 生成一个查询计划。
只能使用 linked_entities 中出现的实体，不能新增实体。
只能使用 schema 中给出的 action、property、relation、label。

如果提供了 conversation_history，你需要结合历史对话理解当前问题的含义。
例如：
- 用户之前问"感冒吃什么药"，当前问"那高血压呢"，应理解为查询"高血压的常用药品"。
- 用户之前问了某个疾病，当前问"它的病因呢"，应将"它"替换为之前提到的疾病。

如果提供了 memory_context，你需要优先参考：
- current_topic：当前对话主题实体
- referenced_result：用户提到“第一个/第二个/最后一个”时对应的结果实体
- intent_hint：从当前问句规则识别出的意图提示
- last_query_plan：上一轮查询计划

输出 query_property 示例：
{
  "action": "query_property",
  "subject": {"name": "高血压", "label": "Disease"},
  "property": "cause"
}

输出 query_relation 示例：
{
  "action": "query_relation",
  "subject": {"name": "高血压", "label": "Disease"},
  "relation": "no_eat",
  "direction": "outgoing"
}

输出 query_relation_chain 示例：
{
  "action": "query_relation_chain",
  "subject": {"name": "流鼻涕", "label": "Symptom"},
  "chain_template": "symptom_to_drug",
  "steps": [
    {"relation": "has_symptom", "direction": "incoming"},
    {"relation": "common_drug", "direction": "outgoing"}
  ]
}

direction 说明：
- outgoing 表示从 subject 指向目标节点，例如 Disease -> no_eat -> Food
- incoming 表示从目标节点反查 subject，例如 Disease -> has_symptom -> Symptom，用户给的是 Symptom

多跳查询只能使用 schema.chain_templates 中定义的固定模板，不能自行组合路径。

如果无法判断，输出：
{}
""".strip()

    def debug_print(self, name, value):
        if self.debug:
            print("[IntentPlanner] {0}: {1}".format(name, value))

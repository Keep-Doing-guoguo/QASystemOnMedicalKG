try:
    from llm_based.schema import (
        PROPERTY_QUERIES,
        RELATION_QUERIES,
        SUPPORTED_ACTIONS,
        schema_for_prompt,
    )
except ModuleNotFoundError:
    from schema import (
        PROPERTY_QUERIES,
        RELATION_QUERIES,
        SUPPORTED_ACTIONS,
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

    def plan(self, question, linked_entities):
        self.debug_print("question", question)
        self.debug_print("linked_entities", linked_entities)
        # 没有实体就不让 LLM 规划，避免凭空生成图谱查询。
        if not linked_entities:
            self.debug_print("skip_reason", "No linked entities.")
            return {}

        # 把用户问题、已识别实体和 schema 一起交给 LLM。
        plan = self.llm_client.chat_json(
            self._system_prompt(),
            {
                "question": question,
                "linked_entities": linked_entities,
                "schema": schema_for_prompt(),
            },
        )
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

    def _system_prompt(self):
        # 提示词明确要求只输出 JSON 查询计划，不回答医学问题。
        return """
你是医疗知识图谱问答系统的查询规划器，只输出 JSON，不回答医学问题。

你需要根据用户问题、已识别实体和图谱 schema 生成一个查询计划。
只能使用 linked_entities 中出现的实体，不能新增实体。
只能使用 schema 中给出的 action、property、relation、label。

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

direction 说明：
- outgoing 表示从 subject 指向目标节点，例如 Disease -> no_eat -> Food
- incoming 表示从目标节点反查 subject，例如 Disease -> has_symptom -> Symptom，用户给的是 Symptom

如果无法判断，输出：
{}
""".strip()

    def debug_print(self, name, value):
        if self.debug:
            print("[IntentPlanner] {0}: {1}".format(name, value))

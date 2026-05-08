#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 18:20
@source from: 
"""
try:
    from llm_base.schema import CHAIN_TEMPLATES, PROPERTY_QUERIES, RELATION_QUERIES
except ModuleNotFoundError:
    from schema import CHAIN_TEMPLATES, PROPERTY_QUERIES, RELATION_QUERIES

class CypherBuilder:
    """把 LLM 查询计划转换成 Neo4j Cypher。

    输入是 IntentPlanner 产生的结构化 plan，输出是：
    1. cypher 字符串
    2. parameters 参数字典
    """

    def __init__(self):
        self.debug = True

    def build(self, plan):
        self.debug_print("plan", plan)
        # 根据 action 分流到属性查询或关系查询。
        action = plan.get("action")
        if action == "query_property":
            return self._build_property_query(plan)
        if action == "query_relation":
            return self._build_relation_query(plan)
        if action == "query_relation_chain":
            return self._build_relation_chain_query(plan)
        self.debug_print("skip_reason", "Unsupported action: {0}".format(action))
        return "", {}

    def _build_property_query(self, plan):
        """构建 Disease 属性查询，例如 Disease.cause / Disease.prevent。"""
        property_name = plan["property"]
        property_schema = PROPERTY_QUERIES[property_name]
        subject = plan["subject"]
        # schema 中限制了哪些 label 才能查哪些属性。
        if subject["label"] != property_schema["label"]:
            self.debug_print("property_label_mismatch", {
                "subject_label": subject["label"],
                "expected_label": property_schema["label"],
            })
            return "", {}

        # label / property 来自白名单 schema，可以拼进 Cypher；
        # 用户输入的实体名放进 parameters，避免直接拼接用户内容。
        cypher = (
            "MATCH (s:{label}) "
            "WHERE s.name = $subject_name "
            "RETURN s.name AS subject, $property_name AS field, "
            "s.{property_name} AS value"
        ).format(label=subject["label"], property_name=property_name)
        parameters = {
            "subject_name": subject["name"],
            "property_name": property_schema["name"],
        }
        self.debug_print("cypher", cypher)
        self.debug_print("parameters", parameters)
        return cypher, parameters

    def _build_relation_query(self, plan):
        """构建节点关系查询，支持 outgoing 和 incoming 两个方向。"""
        relation = plan["relation"]
        relation_schema = RELATION_QUERIES[relation]
        subject = plan["subject"]
        direction = plan.get("direction", "outgoing")

        if direction == "outgoing":
            # 正向查询：subject 是关系起点，例如 Disease -> no_eat -> Food。
            if subject["label"] != relation_schema["start_label"]:
                self.debug_print("relation_label_mismatch", {
                    "direction": direction,
                    "subject_label": subject["label"],
                    "expected_label": relation_schema["start_label"],
                })
                return "", {}
            cypher = (
                "MATCH (s:{start_label})-[r:{relation}]->(o:{end_label}) "
                "WHERE s.name = $subject_name "
                "RETURN s.name AS subject, type(r) AS relation, "
                "r.name AS relation_name, o.name AS object"
            ).format(
                start_label=relation_schema["start_label"],
                relation=relation,
                end_label=relation_schema["end_label"],
            )
        else:
            # 反向查询：subject 是关系终点，例如 Food 反查 Disease。
            if subject["label"] != relation_schema["end_label"]:
                self.debug_print("relation_label_mismatch", {
                    "direction": direction,
                    "subject_label": subject["label"],
                    "expected_label": relation_schema["end_label"],
                })
                return "", {}
            cypher = (
                "MATCH (o:{start_label})-[r:{relation}]->(s:{end_label}) "
                "WHERE s.name = $subject_name "
                "RETURN s.name AS subject, type(r) AS relation, "
                "r.name AS relation_name, o.name AS object"
            ).format(
                start_label=relation_schema["start_label"],
                relation=relation,
                end_label=relation_schema["end_label"],
            )

        # subject_name 始终作为参数传入，不直接拼接。
        parameters = {"subject_name": subject["name"]}
        self.debug_print("cypher", cypher)
        self.debug_print("parameters", parameters)
        return cypher, parameters

    def _build_relation_chain_query(self, plan):
        subject = plan["subject"]
        steps = plan.get("steps", [])
        template_name = plan.get("chain_template")
        template = CHAIN_TEMPLATES.get(template_name)
        if not template:
            self.debug_print("chain_reject", "Unknown chain template.")
            return "", {}
        if len(steps) != len(template["steps"]):
            self.debug_print("chain_reject", "Chain length does not match template.")
            return "", {}

        current_alias = "v0"
        current_label = subject["label"]
        match_parts = []
        return_fields = ["v0.name AS subject"]
        edge_fields = []

        for index, step in enumerate(steps, start=1):
            relation = step["relation"]
            direction = step["direction"]
            relation_schema = RELATION_QUERIES[relation]
            next_alias = "v{0}".format(index)
            relation_alias = "r{0}".format(index)

            if direction == "outgoing":
                if current_label != relation_schema["start_label"]:
                    self.debug_print("chain_label_mismatch", {
                        "step": index,
                        "direction": direction,
                        "current_label": current_label,
                        "expected_label": relation_schema["start_label"],
                    })
                    return "", {}
                next_label = relation_schema["end_label"]
                match_parts.append(
                    "({0}:{1})-[{2}:{3}]->({4}:{5})".format(
                        current_alias, current_label, relation_alias, relation, next_alias, next_label
                    )
                )
            else:
                if current_label != relation_schema["end_label"]:
                    self.debug_print("chain_label_mismatch", {
                        "step": index,
                        "direction": direction,
                        "current_label": current_label,
                        "expected_label": relation_schema["end_label"],
                    })
                    return "", {}
                next_label = relation_schema["start_label"]
                match_parts.append(
                    "({4}:{5})-[{2}:{3}]->({0}:{1})".format(
                        current_alias, current_label, relation_alias, relation, next_alias, next_label
                    )
                )

            return_fields.append("{0}.name AS node{1}".format(next_alias, index))
            return_fields.append("type({0}) AS relation{1}".format(relation_alias, index))
            return_fields.append("{0}.name AS relation_name{1}".format(relation_alias, index))
            edge_fields.append((current_alias, next_alias, direction))
            current_alias = next_alias
            current_label = next_label

        return_fields.append("{0}.name AS object".format(current_alias))
        cypher = (
            "MATCH " + ", ".join(match_parts) +
            " WHERE v0.name = $subject_name " +
            " RETURN " + ", ".join(return_fields)
        )
        parameters = {"subject_name": subject["name"]}
        self.debug_print("cypher", cypher)
        self.debug_print("parameters", parameters)
        return cypher, parameters

    def debug_print(self, name, value):
        if self.debug:
            print("[CypherBuilder] {0}: {1}".format(name, value))

















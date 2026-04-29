#!/usr/bin/env python3
# coding: utf-8

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_based.context_resolver import ContextResolver
from llm_based.intent_planner import IntentPlanner


class DummyLLMClient:
    def __init__(self, responses):
        self.responses = responses
        self.index = 0

    def chat_json(self, system_prompt, user_payload):
        response = self.responses[self.index]
        self.index += 1
        return response


def load_cases():
    path = Path(__file__).with_name("llm_based_cases.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    cases = load_cases()
    fake_responses = [
        {"action": "query_relation", "subject": {"name": "高血压", "label": "Disease"}, "relation": "no_eat", "direction": "outgoing"},
        {"action": "query_relation", "subject": {"name": "高血压", "label": "Disease"}, "relation": "do_eat", "direction": "outgoing"},
        {"action": "query_property", "subject": {"name": "高血压", "label": "Disease"}, "property": "cause"},
        {"action": "query_property", "subject": {"name": "糖尿病", "label": "Disease"}, "property": "cure_way"},
        {"action": "query_relation", "subject": {"name": "流鼻涕", "label": "Symptom"}, "relation": "has_symptom", "direction": "incoming"},
        {"action": "query_relation", "subject": {"name": "板蓝根颗粒", "label": "Drug"}, "relation": "common_drug", "direction": "incoming"},
        {"action": "query_property", "subject": {"name": "高血压", "label": "Disease"}, "property": "cause"},
        {"action": "query_property", "subject": {"name": "糖尿病", "label": "Disease"}, "property": "cure_way"},
        {"action": "query_relation", "subject": {"name": "阿莫西林", "label": "Drug"}, "relation": "common_drug", "direction": "incoming"},
        {"action": "query_relation_chain", "subject": {"name": "流鼻涕", "label": "Symptom"}, "chain_template": "symptom_to_drug", "steps": [{"relation": "has_symptom", "direction": "incoming"}, {"relation": "common_drug", "direction": "outgoing"}]},
        {"action": "query_relation_chain", "subject": {"name": "流鼻涕", "label": "Symptom"}, "chain_template": "symptom_to_check", "steps": [{"relation": "has_symptom", "direction": "incoming"}, {"relation": "need_check", "direction": "outgoing"}]},
        {"action": "query_relation_chain", "subject": {"name": "鹅肉", "label": "Food"}, "chain_template": "food_to_drug", "steps": [{"relation": "do_eat", "direction": "incoming"}, {"relation": "common_drug", "direction": "outgoing"}]},
    ]
    planner = IntentPlanner(DummyLLMClient(fake_responses))
    resolver = ContextResolver()
    passed = 0
    category_stats = {}

    for case in cases:
        category = case.get("category", "uncategorized")
        category_stats.setdefault(category, {"passed": 0, "total": 0})
        category_stats[category]["total"] += 1
        linked = []
        if "高血压" in case["question"]:
            linked = [{"name": "高血压", "labels": ["Disease"]}]
        elif "糖尿病" in case["question"]:
            linked = [{"name": "糖尿病", "labels": ["Disease"]}]
        elif "流鼻涕" in case["question"]:
            linked = [{"name": "流鼻涕", "labels": ["Symptom"]}]
        elif "感冒" in case["question"]:
            linked = [{"name": "感冒", "labels": ["Disease"]}]
        elif "板蓝根颗粒" in case["question"]:
            linked = [{"name": "板蓝根颗粒", "labels": ["Drug"]}]
        elif "鹅肉" in case["question"]:
            linked = [{"name": "鹅肉", "labels": ["Food"]}]

        history = case.get("history", [])
        resolved = resolver.resolve(case["question"], linked, history)
        plan = planner.plan(case["question"], resolved["resolved_entities"], history=history, memory_context=resolved)

        ok = True
        if case.get("expect_plan_action") and plan.get("action") != case["expect_plan_action"]:
            ok = False
        if case.get("expect_relation") and plan.get("relation") != case["expect_relation"]:
            ok = False
        if case.get("expect_property") and plan.get("property") != case["expect_property"]:
            ok = False
        if case.get("expect_direction") and plan.get("direction") != case["expect_direction"]:
            ok = False
        if case.get("expect_chain_template") and plan.get("chain_template") != case["expect_chain_template"]:
            ok = False
        if case.get("expect_memory_subject"):
            first = resolved["resolved_entities"][0]["name"] if resolved["resolved_entities"] else ""
            if first != case["expect_memory_subject"]:
                ok = False
        if case.get("expect_referenced_result"):
            ref = resolved.get("referenced_result", {}).get("name")
            if ref != case["expect_referenced_result"]:
                ok = False

        print(("PASS" if ok else "FAIL"), case["question"], plan)
        if ok:
            passed += 1
            category_stats[category]["passed"] += 1

    print("summary: {0}/{1}".format(passed, len(cases)))
    for category, stats in sorted(category_stats.items()):
        print("category {0}: {1}/{2}".format(category, stats["passed"], stats["total"]))


if __name__ == "__main__":
    main()

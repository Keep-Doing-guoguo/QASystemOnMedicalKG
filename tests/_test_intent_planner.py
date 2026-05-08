#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 17:53
@source from: 
"""
#!/usr/bin/env python3
# coding: utf-8

"""
Run IntentPlanner cases manually without unittest.

Usage:
  python scripts/run_intent_planner_cases.py
  python scripts/run_intent_planner_cases.py --question "为什么会得高血压？" --entity-name "高血压" --entity-label Disease --llm-plan '{"action":"query_property","subject":{"name":"高血压","label":"Disease"},"property":"cause"}'
  python scripts/run_intent_planner_cases.py --question "流鼻涕可能是什么病？" --entity-name "流鼻涕" --entity-label Symptom --llm-plan '{"action":"query_relation","subject":{"name":"流鼻涕","label":"Symptom"},"relation":"bad_relation","direction":"incoming"}'
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_base.intent_planner import IntentPlanner


class DummyLLMClient:
    """Return a fixed JSON plan and record the prompt payload for inspection."""

    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.last_system_prompt = ""
        self.last_user_payload = {}

    def chat_json(self, system_prompt, user_payload):
        self.calls += 1
        self.last_system_prompt = system_prompt
        self.last_user_payload = user_payload
        return self.result


def main():
    args = parse_args()
    if args.llm_plan:
        run_custom_question(args)
        return

    cases = [
        valid_property_plan,#验证正确的
        invalid_relation_falls_back,#验证fallback
        valid_relation_plan,#验证关系
        valid_chain_plan,#
        no_entities_skips_planning,
        history_and_memory_context_are_sent_to_llm,
    ]

    passed = 0
    for case in cases:
        ok = run_case(case)
        if ok:
            passed += 1

    print()
    print("Result: {0}/{1} passed".format(passed, len(cases)))
    if passed != len(cases):
        raise SystemExit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Manually run IntentPlanner cases.")
    parser.add_argument(
        "--question",
        default="为什么会得高血压？",
        help="Question to plan. Used with --llm-plan.",
    )
    parser.add_argument(
        "--entity-name",
        default="高血压",
        help="Linked entity name. Used with --llm-plan.",
    )
    parser.add_argument(
        "--entity-label",
        default="Disease",
        help="Linked entity label. Used with --llm-plan.",
    )
    parser.add_argument(
        "--llm-plan",
        help="JSON string returned by DummyLLMClient. If omitted, built-in cases are executed.",
    )
    parser.add_argument(
        "--with-history",
        action="store_true",
        help="Send fake conversation history and memory_context to planner.",
    )
    return parser.parse_args()


def run_custom_question(args):
    llm_plan = json.loads(args.llm_plan)
    linked_entities = [entity(args.entity_name, args.entity_label)]
    history = sample_history(args.entity_name) if args.with_history else None
    memory_context = sample_memory_context(args.entity_name, args.entity_label) if args.with_history else None

    llm = DummyLLMClient(llm_plan)
    planner = IntentPlanner(llm)
    plan = planner.plan(
        args.question,
        linked_entities,
        history=history,
        memory_context=memory_context,
    )

    print("question:", args.question)
    print("linked_entities:")
    print_json(linked_entities)
    print("llm_raw_plan:")
    print_json(llm_plan)
    print("normalized_or_fallback_plan:")
    print_json(plan)
    print("llm_calls:", llm.calls)
    print("payload_keys:", sorted(llm.last_user_payload.keys()) if llm.last_user_payload else [])
    if args.with_history:
        print("conversation_history:")
        print(llm.last_user_payload.get("conversation_history", ""))
        print("memory_context:")
        print_json(llm.last_user_payload.get("memory_context", {}))


def run_case(case_func):
    print()
    print("=" * 80)
    print(case_func.__name__)
    print("=" * 80)
    try:
        data = case_func()
    except Exception as exc:
        print("FAIL:", exc)
        return False

    print("question:", data["question"])
    print("linked_entities:")
    print_json(data["linked_entities"])
    print("llm_raw_plan:")
    print_json(data["llm_raw_plan"])
    print("final_plan:")
    print_json(data["final_plan"])
    print("llm_calls:", data["llm_calls"])
    print("checks:")
    for item in data["checks"]:
        print("- {0}: {1}".format(item["name"], "PASS" if item["ok"] else "FAIL"))

    ok = all(item["ok"] for item in data["checks"])
    print("status:", "PASS" if ok else "FAIL")
    return ok


def valid_property_plan():
    question = "为什么会得高血压？"
    raw = {
        "action": "query_property",
        "subject": {"name": "高血压", "label": "Disease"},
        "property": "cause",
    }
    data = execute(question, [entity("高血压", "Disease")], raw)
    plan = data["final_plan"]
    data["checks"] = [
        check("action is query_property", plan.get("action") == "query_property"),
        check("property is cause", plan.get("property") == "cause"),
        check("llm called once", data["llm_calls"] == 1),
    ]
    return data


def invalid_relation_falls_back():
    question = "流鼻涕可能是什么病？"
    raw = {
        "action": "query_relation",
        "subject": {"name": "流鼻涕", "label": "Symptom"},
        "relation": "bad_relation",
        "direction": "incoming",
    }
    data = execute(question, [entity("流鼻涕", "Symptom")], raw)
    plan = data["final_plan"]
    data["checks"] = [
        check("fallback action is query_relation", plan.get("action") == "query_relation"),
        check("fallback relation is has_symptom", plan.get("relation") == "has_symptom"),
        check("fallback direction is incoming", plan.get("direction") == "incoming"),
    ]
    return data


def valid_relation_plan():
    question = "高血压不能吃什么？"
    raw = {
        "action": "query_relation",
        "subject": {"name": "高血压", "label": "Disease"},
        "relation": "no_eat",
        "direction": "outgoing",
    }
    data = execute(question, [entity("高血压", "Disease")], raw)
    plan = data["final_plan"]
    data["checks"] = [
        check("action is query_relation", plan.get("action") == "query_relation"),
        check("relation is no_eat", plan.get("relation") == "no_eat"),
        check("direction is outgoing", plan.get("direction") == "outgoing"),
    ]
    return data


def valid_chain_plan():
    question = "流鼻涕吃什么药？"
    raw = {
        "action": "query_relation_chain",
        "subject": {"name": "流鼻涕", "label": "Symptom"},
        "chain_template": "symptom_to_drug",
        "steps": [
            {"relation": "has_symptom", "direction": "incoming"},
            {"relation": "common_drug", "direction": "outgoing"},
        ],
    }
    data = execute(question, [entity("流鼻涕", "Symptom")], raw)
    plan = data["final_plan"]
    data["checks"] = [
        check("action is query_relation_chain", plan.get("action") == "query_relation_chain"),
        check("chain_template is symptom_to_drug", plan.get("chain_template") == "symptom_to_drug"),
        check("steps length is 2", len(plan.get("steps", [])) == 2),
    ]
    return data


def no_entities_skips_planning():
    question = "它的病因呢？"
    raw = {
        "action": "query_property",
        "subject": {"name": "高血压", "label": "Disease"},
        "property": "cause",
    }
    data = execute(question, [], raw)
    data["checks"] = [
        check("plan is empty", data["final_plan"] == {}),
        check("llm is not called", data["llm_calls"] == 0),
    ]
    return data


def history_and_memory_context_are_sent_to_llm():
    question = "那它适合吃什么？"
    raw = {
        "action": "query_relation",
        "subject": {"name": "高血压", "label": "Disease"},
        "relation": "do_eat",
        "direction": "outgoing",
    }
    history = sample_history("高血压")
    memory_context = sample_memory_context("高血压", "Disease")
    data = execute(question, [entity("高血压", "Disease")], raw, history, memory_context)
    payload = data["payload"]
    data["checks"] = [
        check("conversation_history is sent", "conversation_history" in payload),
        check("memory_context is sent", "memory_context" in payload),
        check("memory current_topic is 高血压", payload["memory_context"]["current_topic"]["name"] == "高血压"),
        check("final relation is do_eat", data["final_plan"].get("relation") == "do_eat"),
    ]
    return data


def execute(question, linked_entities, raw_plan, history=None, memory_context=None):
    llm = DummyLLMClient(raw_plan)
    planner = IntentPlanner(llm)
    final_plan = planner.plan(
        question,
        linked_entities,
        history=history,
        memory_context=memory_context,
    )
    return {
        "question": question,
        "linked_entities": linked_entities,
        "llm_raw_plan": raw_plan,
        "final_plan": final_plan,
        "llm_calls": llm.calls,
        "payload": llm.last_user_payload,
        "checks": [],
    }


def entity(name, label):
    return {
        "name": name,
        "types": [type_for_label(label)],
        "labels": [label],
    }


def type_for_label(label):
    return {
        "Disease": "disease",
        "Symptom": "symptom",
        "Drug": "drug",
        "Food": "food",
        "Check": "check",
    }.get(label, "")


def sample_history(topic):
    return [
        {"role": "user", "question": topic + "不能吃什么？"},
        {"role": "assistant", "answer": topic + "患者需要注意饮食。"},
    ]


def sample_memory_context(topic, label):
    return {
        "current_topic": {"name": topic, "label": label},
        "last_query_plan": {
            "action": "query_relation",
            "subject": {"name": topic, "label": label},
            "relation": "no_eat",
            "direction": "outgoing",
        },
        "recent_result_entities": [],
    }


def check(name, ok):
    return {"name": name, "ok": bool(ok)}


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

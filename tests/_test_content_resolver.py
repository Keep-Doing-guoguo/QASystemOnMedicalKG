#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 16:59
@source from: 
"""
#!/usr/bin/env python3
# coding: utf-8

"""
Run ContextResolver cases manually without unittest.

Usage:
  python scripts/run_context_resolver_cases.py
  python scripts/run_context_resolver_cases.py --question "它的病因呢？" --topic "高血压"
  python scripts/run_context_resolver_cases.py --question "第二个药还能治什么病？" --topic "感冒" --with-results
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_base.content_resolver import ContextResolver


def main():
    args = parse_args()
    if args.question:
        run_custom_question(args)
        return

    cases = [
        followup_uses_current_topic,
        ordinal_reference_uses_recent_results,
        existing_entity_is_kept_and_intent_is_inferred,
        short_question_without_entity_is_followup,
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
    parser = argparse.ArgumentParser(description="Manually run ContextResolver cases.")
    parser.add_argument(
        "--question",
        help="Question to resolve. If omitted, built-in cases are executed.",
    )
    parser.add_argument(
        "--topic",
        default="高血压",
        help="Topic entity stored in fake history. Default: 高血压",
    )
    parser.add_argument(
        "--label",
        default="Disease",
        help="Topic label stored in fake history. Default: Disease",
    )
    parser.add_argument(
        "--linked-name",
        default="",
        help="Optional entity already linked from the current question.",
    )
    parser.add_argument(
        "--linked-label",
        default="Disease",
        help="Label for --linked-name. Default: Disease",
    )
    parser.add_argument(
        "--with-results",
        action="store_true",
        help="Add fake recent result entities for ordinal reference tests.",
    )
    return parser.parse_args()


def run_custom_question(args):
    resolver = ContextResolver()
    linked_entities = []
    if args.linked_name:
        linked_entities.append(entity(args.linked_name, args.linked_label))
    history = history_with_topic(args.topic, args.label, with_results=args.with_results)
    resolved = resolver.resolve(args.question, linked_entities, history)

    print("question:", args.question)
    print("linked_entities:")
    print_json(linked_entities)
    print("history:")
    print_json(history)
    print("resolved:")
    print_json(resolved)


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
    print("resolved:")
    print_json(data["resolved"])
    print("checks:")
    for check in data["checks"]:
        print("- {0}: {1}".format(check["name"], "PASS" if check["ok"] else "FAIL"))

    ok = all(check["ok"] for check in data["checks"])
    print("status:", "PASS" if ok else "FAIL")
    return ok


def followup_uses_current_topic():
    resolver = ContextResolver()
    question = "它的病因呢？"
    resolved = resolver.resolve(question, [], history_with_topic("高血压", "Disease"))
    return case_result(
        question,
        resolved,
        [
            check("resolved topic is 高血压", resolved["resolved_entities"][0]["name"] == "高血压"),
            check("intent target is cause", resolved["intent_hint"].get("target") == "cause"),
            check("followup is true", resolved["followup"] is True),
        ],
    )


def ordinal_reference_uses_recent_results():
    resolver = ContextResolver()
    question = "第二个药还能治什么病？"
    resolved = resolver.resolve(question, [], history_with_topic("感冒", "Disease", with_results=True))
    return case_result(
        question,
        resolved,
        [
            check("referenced result is 阿莫西林", resolved["referenced_result"]["name"] == "阿莫西林"),
            check("resolved entity includes 阿莫西林", any(e["name"] == "阿莫西林" for e in resolved["resolved_entities"])),
            check("current topic is 感冒", resolved["current_topic"]["name"] == "感冒"),
        ],
    )


def existing_entity_is_kept_and_intent_is_inferred():
    resolver = ContextResolver()
    question = "糖尿病怎么治疗？"
    linked_entities = [entity("糖尿病", "Disease")]
    resolved = resolver.resolve(question, linked_entities, history_with_topic("高血压", "Disease"))
    return case_result(
        question,
        resolved,
        [
            check("existing entity is kept", resolved["resolved_entities"][0]["name"] == "糖尿病"),
            check("history topic still available", resolved["current_topic"]["name"] == "高血压"),
            check("intent target is cure_way", resolved["intent_hint"].get("target") == "cure_way"),
        ],
    )


def short_question_without_entity_is_followup():
    resolver = ContextResolver()
    question = "怎么治？"
    resolved = resolver.resolve(question, [], history_with_topic("高血压", "Disease"))
    return case_result(
        question,
        resolved,
        [
            check("short question is followup", resolved["followup"] is True),
            check("resolved topic is 高血压", resolved["resolved_entities"][0]["name"] == "高血压"),
        ],
    )


def history_with_topic(topic, label, with_results=False):
    turn = {
        "role": "assistant",
        "answer": topic + "的查询结果。",
        "plan": {
            "action": "query_relation",
            "subject": {"name": topic, "label": label},
            "relation": "common_drug",
            "direction": "outgoing",
        },
        "result_entities": [],
    }
    if with_results:
        turn["result_entities"] = [
            {"name": "板蓝根颗粒", "label": "Drug"},
            {"name": "阿莫西林", "label": "Drug"},
            {"name": "感冒灵颗粒", "label": "Drug"},
        ]
    return [{"role": "user", "question": topic + "要吃什么药？"}, turn]


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


def case_result(question, resolved, checks):
    return {
        "question": question,
        "resolved": resolved,
        "checks": checks,
    }


def check(name, ok):
    return {"name": name, "ok": bool(ok)}


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

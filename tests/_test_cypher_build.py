#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 18:34
@source from: 
"""
#!/usr/bin/env python3
# coding: utf-8

"""
Run CypherBuilder cases manually without unittest.

Usage:
  python scripts/run_cypher_builder_cases.py
  python scripts/run_cypher_builder_cases.py --plan '{"action":"query_property","subject":{"name":"高血压","label":"Disease"},"property":"cause"}'
  python scripts/run_cypher_builder_cases.py --plan '{"action":"query_relation","subject":{"name":"高血压","label":"Disease"},"relation":"no_eat","direction":"outgoing"}'
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_base.cypher_builder import CypherBuilder


def main():
    args = parse_args()
    if args.plan:
        run_custom_plan(args)
        return
    run_builtin_cases()


def parse_args():
    parser = argparse.ArgumentParser(description="Manually run CypherBuilder cases.")
    parser.add_argument(
        "--plan",
        help="JSON query plan. If omitted, built-in cases are executed.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable CypherBuilder debug output.",
    )
    return parser.parse_args()


def run_custom_plan(args):
    plan = json.loads(args.plan)
    builder = CypherBuilder()
    builder.debug = args.debug
    cypher, parameters = builder.build(plan)

    print("plan:")
    print_json(plan)
    print("cypher:", cypher)
    print("parameters:")
    print_json(parameters)


def run_builtin_cases():
    cases = [
        # 测试属性查询：Disease 属性 plan 是否能生成 MATCH + RETURN 属性值的 Cypher。
        property_query_builds_cypher,
        # 测试正向关系查询：Disease -> relation -> Entity 的 Cypher 生成。
        relation_outgoing_query_builds_cypher,
        # 测试反向关系查询：从关系终点实体反查起点实体的 Cypher 生成。
        relation_incoming_query_builds_cypher,
        # 测试多跳链路查询：按固定 chain_template 生成多段 MATCH。
        relation_chain_query_builds_cypher,
        # 测试属性查询 label 不匹配时应拒绝生成 Cypher。
        property_label_mismatch_returns_empty,
        # 测试未知 action 时应返回空 Cypher 和空参数。
        unsupported_action_returns_empty,
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

    print("plan:")
    print_json(data["plan"])
    print("cypher:", data["cypher"])
    print("parameters:")
    print_json(data["parameters"])
    print("checks:")
    for item in data["checks"]:
        print("- {0}: {1}".format(item["name"], "PASS" if item["ok"] else "FAIL"))

    ok = all(item["ok"] for item in data["checks"])
    print("status:", "PASS" if ok else "FAIL")
    return ok


def property_query_builds_cypher():
    plan = {
        "action": "query_property",
        "subject": {"name": "高血压", "label": "Disease"},
        "property": "cause",
    }
    cypher, parameters = build(plan)
    return case_result(
        plan,
        cypher,
        parameters,
        [
            check("cypher has Disease label", "MATCH (s:Disease)" in cypher),
            check("cypher returns property value", "s.cause AS value" in cypher),
            check("subject_name is 高血压", parameters.get("subject_name") == "高血压"),
            check("property_name is 疾病病因", parameters.get("property_name") == "疾病病因"),
        ],
    )


def relation_outgoing_query_builds_cypher():
    plan = {
        "action": "query_relation",
        "subject": {"name": "高血压", "label": "Disease"},
        "relation": "no_eat",
        "direction": "outgoing",
    }
    cypher, parameters = build(plan)
    return case_result(
        plan,
        cypher,
        parameters,
        [
            check("cypher has outgoing no_eat", "-[r:no_eat]->" in cypher),
            check("cypher starts from Disease", "MATCH (s:Disease)" in cypher),
            check("subject_name is 高血压", parameters.get("subject_name") == "高血压"),
        ],
    )


def relation_incoming_query_builds_cypher():
    plan = {
        "action": "query_relation",
        "subject": {"name": "蜂蜜", "label": "Food"},
        "relation": "no_eat",
        "direction": "incoming",
    }
    cypher, parameters = build(plan)
    return case_result(
        plan,
        cypher,
        parameters,
        [
            check("cypher has incoming pattern", "MATCH (o:Disease)-[r:no_eat]->(s:Food)" in cypher),
            check("subject_name is 蜂蜜", parameters.get("subject_name") == "蜂蜜"),
        ],
    )


def relation_chain_query_builds_cypher():
    plan = {
        "action": "query_relation_chain",
        "subject": {"name": "流鼻涕", "label": "Symptom"},
        "chain_template": "symptom_to_drug",
        "steps": [
            {"relation": "has_symptom", "direction": "incoming"},
            {"relation": "common_drug", "direction": "outgoing"},
        ],
    }
    cypher, parameters = build(plan)
    return case_result(
        plan,
        cypher,
        parameters,
        [
            check("cypher contains has_symptom", "has_symptom" in cypher),
            check("cypher contains common_drug", "common_drug" in cypher),
            check("cypher returns object", "AS object" in cypher),
            check("subject_name is 流鼻涕", parameters.get("subject_name") == "流鼻涕"),
        ],
    )


def property_label_mismatch_returns_empty():
    plan = {
        "action": "query_property",
        "subject": {"name": "流鼻涕", "label": "Symptom"},
        "property": "cause",
    }
    cypher, parameters = build(plan)
    return case_result(
        plan,
        cypher,
        parameters,
        [
            check("cypher is empty", cypher == ""),
            check("parameters is empty", parameters == {}),
        ],
    )


def unsupported_action_returns_empty():
    plan = {
        "action": "unknown_action",
        "subject": {"name": "高血压", "label": "Disease"},
    }
    cypher, parameters = build(plan)
    return case_result(
        plan,
        cypher,
        parameters,
        [
            check("cypher is empty", cypher == ""),
            check("parameters is empty", parameters == {}),
        ],
    )


def build(plan):
    builder = CypherBuilder()
    builder.debug = False
    return builder.build(plan)


def case_result(plan, cypher, parameters, checks):
    return {
        "plan": plan,
        "cypher": cypher,
        "parameters": parameters,
        "checks": checks,
    }


def check(name, ok):
    return {"name": name, "ok": bool(ok)}


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

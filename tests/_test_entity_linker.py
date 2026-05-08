#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 18:23
@source from: 
"""
#!/usr/bin/env python3
# coding: utf-8

"""
Run EntityLinker cases manually without unittest.

Usage:
  python scripts/run_entity_linker_cases.py
  python scripts/run_entity_linker_cases.py --question "高血压不能吃什么？"
  python scripts/run_entity_linker_cases.py --validate-name "高血压" --validate-label Disease
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_base.entity_link import EntityLinker


def main():
    args = parse_args()
    linker = EntityLinker()
    linker.debug = args.debug

    if args.validate_name:
        run_validate(linker, args.validate_name, args.validate_label)
        return

    if args.question:
        run_custom_question(linker, args.question)
        return

    run_builtin_cases(linker)


def parse_args():
    parser = argparse.ArgumentParser(description="Manually run EntityLinker cases.")
    parser.add_argument(
        "--question",
        help="Question to link. If omitted, built-in cases are executed.",
    )
    parser.add_argument(
        "--validate-name",
        default="",
        help="Entity name to validate.",
    )
    parser.add_argument(
        "--validate-label",
        default="Disease",
        help="Neo4j label to validate. Default: Disease",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable EntityLinker debug output.",
    )
    return parser.parse_args()


def run_custom_question(linker, question):
    linked_entities = linker.link(question)
    print("question:", question)
    print("linked_entities:")
    print_json(linked_entities)


def run_validate(linker, name, label):
    result = linker.validate_entity(name, label)
    print("name:", name)
    print("label:", label)
    print("valid:", result)


def run_builtin_cases(linker):
    cases = [
        disease_long_word_keeps_specific_entity,
        symptom_entity_is_linked,
        drug_entity_is_linked,
        food_entity_is_linked,
        unknown_question_returns_empty,
        validate_existing_disease,
        validate_wrong_label_fails,
    ]

    passed = 0
    for case in cases:
        ok = run_case(linker, case)
        if ok:
            passed += 1

    print()
    print("Result: {0}/{1} passed".format(passed, len(cases)))
    if passed != len(cases):
        raise SystemExit(1)


def run_case(linker, case_func):
    print()
    print("=" * 80)
    print(case_func.__name__)
    print("=" * 80)
    try:
        data = case_func(linker)
    except Exception as exc:
        print("FAIL:", exc)
        return False

    print("question:", data.get("question", ""))
    if "linked_entities" in data:
        print("linked_entities:")
        print_json(data["linked_entities"])
    if "validation" in data:
        print("validation:")
        print_json(data["validation"])
    print("checks:")
    for item in data["checks"]:
        print("- {0}: {1}".format(item["name"], "PASS" if item["ok"] else "FAIL"))

    ok = all(item["ok"] for item in data["checks"])
    print("status:", "PASS" if ok else "FAIL")
    return ok


def disease_long_word_keeps_specific_entity(linker):
    question = "高血压不能吃什么？"
    linked = linker.link(question)
    names = names_of(linked)
    return case_result(
        question,
        linked,
        [
            check("contains 高血压", "高血压" in names),
            check("does not keep contained short word 血压", "血压" not in names),
            check("高血压 label is Disease", has_label(linked, "高血压", "Disease")),
        ],
    )


def symptom_entity_is_linked(linker):
    question = "流鼻涕可能是什么病？"
    linked = linker.link(question)
    return case_result(
        question,
        linked,
        [
            check("contains 流鼻涕", "流鼻涕" in names_of(linked)),
            check("流鼻涕 label is Symptom", has_label(linked, "流鼻涕", "Symptom")),
        ],
    )


def drug_entity_is_linked(linker):
    question = "板蓝根颗粒能治什么病？"
    linked = linker.link(question)
    return case_result(
        question,
        linked,
        [
            check("contains 板蓝根颗粒", "板蓝根颗粒" in names_of(linked)),
            check("板蓝根颗粒 label is Drug", has_label(linked, "板蓝根颗粒", "Drug")),
        ],
    )


def food_entity_is_linked(linker):
    question = "哪些病人不能吃蜂蜜？"
    linked = linker.link(question)
    return case_result(
        question,
        linked,
        [
            check("contains 蜂蜜", "蜂蜜" in names_of(linked)),
            check("蜂蜜 label is Food", has_label(linked, "蜂蜜", "Food")),
        ],
    )


def unknown_question_returns_empty(linker):
    question = "我最近有点不舒服怎么办？"
    linked = linker.link(question)
    return case_result(
        question,
        linked,
        [
            check("no linked entities", linked == []),
        ],
    )


def validate_existing_disease(linker):
    valid = linker.validate_entity("高血压", "Disease")
    return validation_result(
        "高血压",
        "Disease",
        valid,
        [
            check("高血压 is valid Disease", valid is True),
        ],
    )


def validate_wrong_label_fails(linker):
    valid = linker.validate_entity("高血压", "Drug")
    return validation_result(
        "高血压",
        "Drug",
        valid,
        [
            check("高血压 is not Drug", valid is False),
        ],
    )


def case_result(question, linked_entities, checks):
    return {
        "question": question,
        "linked_entities": linked_entities,
        "checks": checks,
    }


def validation_result(name, label, valid, checks):
    return {
        "validation": {
            "name": name,
            "label": label,
            "valid": valid,
        },
        "checks": checks,
    }


def names_of(linked_entities):
    return [item.get("name") for item in linked_entities]


def has_label(linked_entities, name, label):
    for item in linked_entities:
        if item.get("name") == name and label in item.get("labels", []):
            return True
    return False


def check(name, ok):
    return {"name": name, "ok": bool(ok)}


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

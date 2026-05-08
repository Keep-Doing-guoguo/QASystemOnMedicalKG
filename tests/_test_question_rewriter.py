#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/7 22:02
@source from: 
"""


from llm_base.question_rewriter import QuestionRewriter


#!/usr/bin/env python3
# coding: utf-8

"""
Run QuestionRewriter cases manually without unittest.

Usage:
  python scripts/run_question_rewriter_cases.py
  python scripts/run_question_rewriter_cases.py --question "那它适合吃什么？" --topic "高血压"
"""

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_base.question_rewriter import QuestionRewriter


class DummyLLMClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def chat_text(self, system_prompt, user_payload):
        self.calls += 1
        return self.answer


def main():
    args = parse_args()
    if args.question:
        run_custom_question(args)
        return

    cases = [
        no_history_not_rewritten,
        complete_question_not_rewritten,
        pronoun_question_is_rewritten_by_latest_plan_subject,
        followup_question_is_rewritten_by_latest_plan_subject,
        topic_can_be_resolved_from_entities,
        llm_is_used_when_heuristic_cannot_resolve_topic,
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
    parser = argparse.ArgumentParser(description="Manually run QuestionRewriter cases.")
    parser.add_argument(
        "--question",
        help="Question to rewrite. If omitted, built-in cases are executed.",
    )
    parser.add_argument(
        "--topic",
        default="高血压",
        help="Topic entity used to build fake history for custom question. Default: 高血压",
    )
    parser.add_argument(
        "--llm-answer",
        default="",
        help="Dummy LLM answer used when heuristic rewrite cannot resolve the topic.",
    )
    parser.add_argument(
        "--history-mode",
        choices=["plan", "entities", "plain", "empty"],
        default="plan",
        help="Fake history type for custom question. Default: plan",
    )
    return parser.parse_args()


def run_custom_question(args):
    llm = DummyLLMClient(args.llm_answer or args.question)
    rewriter = QuestionRewriter(llm)
    history = build_history(args.topic, args.history_mode)
    rewritten = rewriter.rewrite(args.question, history)

    print("question:", args.question)
    print("topic:", args.topic)
    print("history_mode:", args.history_mode)
    print("history:", history)
    print("rewritten:", rewritten)
    print("llm_calls:", llm.calls)


def run_case(case_func):
    print()
    print("=" * 80)
    print(case_func.__name__)
    print("=" * 80)
    try:
        result = case_func()
    except Exception as exc:
        print("FAIL:", exc)
        return False

    print("question:", result["question"])
    print("rewritten:", result["rewritten"])
    print("expected:", result["expected"])
    print("llm_calls:", result["llm_calls"])
    print("expected_llm_calls:", result["expected_llm_calls"])

    ok = (
        result["rewritten"] == result["expected"]
        and result["llm_calls"] == result["expected_llm_calls"]
    )
    print("status:", "PASS" if ok else "FAIL")
    return ok


def no_history_not_rewritten():
    llm = DummyLLMClient("不应被调用")
    rewriter = QuestionRewriter(llm)
    question = "它的病因呢？"
    rewritten = rewriter.rewrite(question, [])
    return result(question, rewritten, question, llm.calls, 0)


def complete_question_not_rewritten():
    llm = DummyLLMClient("不应被调用")
    rewriter = QuestionRewriter(llm)
    question = "高血压怎么治疗？"
    history = history_with_plan("高血压")
    rewritten = rewriter.rewrite(question, history)
    return result(question, rewritten, question, llm.calls, 0)


def pronoun_question_is_rewritten_by_latest_plan_subject():
    llm = DummyLLMClient("不应被调用")
    rewriter = QuestionRewriter(llm)
    question = "它的病因呢？"
    history = history_with_plan("高血压")
    rewritten = rewriter.rewrite(question, history)
    return result(question, rewritten, "高血压的病因呢？", llm.calls, 0)


def followup_question_is_rewritten_by_latest_plan_subject():
    llm = DummyLLMClient("不应被调用")
    rewriter = QuestionRewriter(llm)
    question = "那它适合吃什么？"
    history = history_with_plan("高血压")
    rewritten = rewriter.rewrite(question, history)
    return result(question, rewritten, "那高血压适合吃什么？", llm.calls, 0)


def topic_can_be_resolved_from_entities():
    llm = DummyLLMClient("不应被调用")
    rewriter = QuestionRewriter(llm)
    question = "它多久能好？"
    history = [
        {"role": "user", "question": "感冒要吃什么药？"},
        {
            "role": "assistant",
            "answer": "感冒可查询常用药。",
            "entities": [
                {"name": "感冒", "types": ["disease"], "labels": ["Disease"]},
            ],
        },
    ]
    rewritten = rewriter.rewrite(question, history)
    return result(question, rewritten, "感冒多久能好？", llm.calls, 0)


def llm_is_used_when_heuristic_cannot_resolve_topic():
    llm = DummyLLMClient("高血压的病因是什么？")
    rewriter = QuestionRewriter(llm)
    question = "它的病因呢？"
    history = [
        {"role": "user", "question": "高血压是什么？"},
        {"role": "assistant", "answer": "高血压是一种常见疾病。"},
    ]
    rewritten = rewriter.rewrite(question, history)
    return result(question, rewritten, "高血压的病因是什么？", llm.calls, 1)


def history_with_plan(subject_name):
    return [
        {"role": "user", "question": subject_name + "不能吃什么？"},
        {
            "role": "assistant",
            "answer": subject_name + "患者需要注意饮食。",
            "plan": {
                "action": "query_relation",
                "subject": {"name": subject_name, "label": "Disease"},
                "relation": "no_eat",
                "direction": "outgoing",
            },
        },
    ]


def history_with_entities(subject_name):
    return [
        {"role": "user", "question": subject_name + "要吃什么药？"},
        {
            "role": "assistant",
            "answer": subject_name + "可查询常用药。",
            "entities": [
                {"name": subject_name, "types": ["disease"], "labels": ["Disease"]},
            ],
        },
    ]


def history_plain(subject_name):
    return [
        {"role": "user", "question": subject_name + "是什么？"},
        {"role": "assistant", "answer": subject_name + "是一种常见疾病。"},
    ]


def build_history(topic, mode):
    if mode == "empty":
        return []
    if mode == "entities":
        return history_with_entities(topic)
    if mode == "plain":
        return history_plain(topic)
    return history_with_plan(topic)


def result(question, rewritten, expected, llm_calls, expected_llm_calls):
    return {
        "question": question,
        "rewritten": rewritten,
        "expected": expected,
        "llm_calls": llm_calls,
        "expected_llm_calls": expected_llm_calls,
    }


if __name__ == "__main__":
    main()



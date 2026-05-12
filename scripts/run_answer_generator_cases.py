#!/usr/bin/env python3
# coding: utf-8

"""
Run AnswerGenerator cases manually without unittest.

Usage:
  python scripts/run_answer_generator_cases.py
  python scripts/run_answer_generator_cases.py --question "高血压不能吃什么？" --plan '{"action":"query_relation","subject":{"name":"高血压","label":"Disease"},"relation":"no_eat","direction":"outgoing"}' --graph-results '[{"object":"咸鸭蛋"},{"object":"鸡肝"}]'
  python scripts/run_answer_generator_cases.py --question "高血压不能吃什么？" --plan '{"action":"query_relation","subject":{"name":"高血压","label":"Disease"},"relation":"no_eat","direction":"outgoing"}' --graph-results '[{"object":"咸鸭蛋"}]' --llm-answer "根据图谱，高血压患者不建议吃咸鸭蛋。"
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_based.answer_generator import AnswerGenerator


class DummyLLMClient:
    """Return fixed text and record payload for manual inspection."""

    def __init__(self, answer=""):
        self.answer = answer
        self.calls = 0
        self.last_system_prompt = ""
        self.last_user_payload = {}

    def chat_text(self, system_prompt, user_payload):
        self.calls += 1
        self.last_system_prompt = system_prompt
        self.last_user_payload = user_payload
        return self.answer


def main():
    args = parse_args()
    if args.plan:
        run_custom_case(args)
        return
    run_builtin_cases()


def parse_args():
    parser = argparse.ArgumentParser(description="Manually run AnswerGenerator cases.")
    parser.add_argument(
        "--question",
        default="高血压不能吃什么？",
        help="Question for custom case.",
    )
    parser.add_argument(
        "--plan",
        help="JSON query plan. If omitted, built-in cases are executed.",
    )
    parser.add_argument(
        "--graph-results",
        default="[]",
        help="JSON graph results for custom case.",
    )
    parser.add_argument(
        "--llm-answer",
        default="",
        help="Dummy LLM answer. Empty means LLM fallback to template.",
    )
    parser.add_argument(
        "--with-history",
        action="store_true",
        help="Send fake conversation history to AnswerGenerator.",
    )
    parser.add_argument(
        "--num-limit",
        type=int,
        default=20,
        help="Max graph result count used by generator. Default: 20",
    )
    return parser.parse_args()


def run_custom_case(args):
    plan = json.loads(args.plan)
    graph_results = json.loads(args.graph_results)
    history = sample_history() if args.with_history else None
    llm = DummyLLMClient(args.llm_answer)
    generator = AnswerGenerator(llm, num_limit=args.num_limit)
    answer = generator.generate(args.question, plan, graph_results, history=history)

    print("question:", args.question)
    print("plan:")
    print_json(plan)
    print("graph_results:")
    print_json(graph_results)
    print("answer:", answer)
    print("llm_calls:", llm.calls)
    print("llm_payload:")
    print_json(llm.last_user_payload)


def run_builtin_cases():
    cases = [
        # 测试图谱结果为空时直接返回兜底回答，不调用 LLM。
        empty_graph_results_returns_fallback,
        # 测试长文本属性查询直接走本地模板，避免把大段文本传给 LLM。
        long_property_uses_template_without_llm,
        # 测试关系查询在 LLM 返回空时使用本地模板生成答案。
        relation_template_used_when_llm_empty,
        # 测试 LLM 返回非空答案时优先使用 LLM 答案。
        llm_answer_is_used_when_available,
        # 测试多跳关系查询的本地模板回答。
        relation_chain_template_answer,
        # 测试 history 会被格式化后传给 LLM。
        history_is_sent_to_llm,
        # 测试长 graph_results value 会被截断后再传给 LLM。
        graph_results_are_truncated_for_llm,
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

    print("question:", data["question"])
    print("plan:")
    print_json(data["plan"])
    print("graph_results:")
    print_json(data["graph_results"])
    print("answer:", data["answer"])
    print("llm_calls:", data["llm_calls"])
    if data.get("llm_payload"):
        print("llm_payload:")
        print_json(data["llm_payload"])
    print("checks:")
    for item in data["checks"]:
        print("- {0}: {1}".format(item["name"], "PASS" if item["ok"] else "FAIL"))

    ok = all(item["ok"] for item in data["checks"])
    print("status:", "PASS" if ok else "FAIL")
    return ok


def empty_graph_results_returns_fallback():
    question = "高血压不能吃什么？"
    plan = relation_plan("高血压", "no_eat")
    data = execute(question, plan, [], llm_answer="不应被调用")
    data["checks"] = [
        check("fallback answer returned", data["answer"] == "当前知识图谱中没有查到相关信息。"),
        check("llm is not called", data["llm_calls"] == 0),
    ]
    return data


def long_property_uses_template_without_llm():
    question = "糖尿病是什么？"
    plan = {
        "action": "query_property",
        "subject": {"name": "糖尿病", "label": "Disease"},
        "property": "desc",
    }
    graph_results = [{"value": "很长的简介" * 80}]
    data = execute(question, plan, graph_results, llm_answer="不应被调用")
    data["checks"] = [
        check("template answer mentions 糖尿病的疾病简介", "糖尿病的疾病简介" in data["answer"]),
        check("llm is not called", data["llm_calls"] == 0),
    ]
    return data


def relation_template_used_when_llm_empty():
    question = "高血压不能吃什么？"
    plan = relation_plan("高血压", "no_eat")
    graph_results = [{"object": "咸鸭蛋"}, {"object": "鸡肝"}, {"object": "咸鸭蛋"}]
    data = execute(question, plan, graph_results, llm_answer="")
    data["checks"] = [
        check("template mentions relation name", "忌食" in data["answer"]),
        check("deduplicates objects", data["answer"].count("咸鸭蛋") == 1),
        check("llm is called once", data["llm_calls"] == 1),
    ]
    return data


def llm_answer_is_used_when_available():
    question = "高血压不能吃什么？"
    plan = relation_plan("高血压", "no_eat")
    graph_results = [{"object": "咸鸭蛋"}]
    llm_answer = "根据当前知识图谱，高血压患者不建议吃咸鸭蛋。"
    data = execute(question, plan, graph_results, llm_answer=llm_answer)
    data["checks"] = [
        check("answer equals llm answer", data["answer"] == llm_answer),
        check("llm is called once", data["llm_calls"] == 1),
    ]
    return data


def relation_chain_template_answer():
    question = "流鼻涕吃什么药？"
    plan = {
        "action": "query_relation_chain",
        "subject": {"name": "流鼻涕", "label": "Symptom"},
        "chain_template": "symptom_to_drug",
    }
    graph_results = [{"object": "板蓝根颗粒"}, {"object": "感冒灵颗粒"}]
    data = execute(question, plan, graph_results, llm_answer="")
    data["checks"] = [
        check("answer mentions two-hop relation", "经过两跳关系" in data["answer"]),
        check("answer includes 板蓝根颗粒", "板蓝根颗粒" in data["answer"]),
    ]
    return data


def history_is_sent_to_llm():
    question = "那它适合吃什么？"
    plan = relation_plan("高血压", "do_eat")
    graph_results = [{"object": "芝麻"}]
    data = execute(
        question,
        plan,
        graph_results,
        llm_answer="根据当前知识图谱，高血压患者适合吃芝麻。",
        history=sample_history(),
    )
    payload = data["llm_payload"]
    data["checks"] = [
        check("conversation_history is sent", "conversation_history" in payload),
        check("history contains user text", "高血压不能吃什么" in payload["conversation_history"]),
    ]
    return data


def graph_results_are_truncated_for_llm():
    question = "高血压怎么治疗？"
    plan = {
        "action": "query_property",
        "subject": {"name": "高血压", "label": "Disease"},
        "property": "cure_way",
    }
    graph_results = [{"value": "治疗方式" * 100}]
    data = execute(question, plan, graph_results, llm_answer="根据图谱，高血压可采用相关治疗方式。")
    payload_value = data["llm_payload"]["graph_results"][0]["value"]
    data["checks"] = [
        check("payload value is truncated", payload_value.endswith("...")),
        check("payload value length is limited", len(payload_value) <= 323),
    ]
    return data


def execute(question, plan, graph_results, llm_answer="", history=None):
    llm = DummyLLMClient(llm_answer)
    generator = AnswerGenerator(llm)
    answer = generator.generate(question, plan, graph_results, history=history)
    return {
        "question": question,
        "plan": plan,
        "graph_results": graph_results,
        "answer": answer,
        "llm_calls": llm.calls,
        "llm_payload": llm.last_user_payload,
        "checks": [],
    }


def relation_plan(subject_name, relation):
    return {
        "action": "query_relation",
        "subject": {"name": subject_name, "label": "Disease"},
        "relation": relation,
        "direction": "outgoing",
    }


def sample_history():
    return [
        {"role": "user", "question": "高血压不能吃什么？"},
        {"role": "assistant", "answer": "高血压患者应避免咸鸭蛋。"},
    ]


def check(name, ok):
    return {"name": name, "ok": bool(ok)}


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

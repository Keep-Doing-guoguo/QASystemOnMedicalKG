#!/usr/bin/env python3
# coding: utf-8

try:
    # 作为包运行时使用绝对导入：python -m llm_based.chatbot_graph
    from llm_based.answer_generator import AnswerGenerator
    from llm_based.cypher_builder import CypherBuilder
    from llm_based.entity_linker import EntityLinker
    from llm_based.graph_client import GraphClient
    from llm_based.intent_planner import IntentPlanner
    from llm_based.llm_client import LLMClient
except ModuleNotFoundError:
    # 直接运行文件时使用当前目录导入：python llm_based/chatbot_graph.py
    from answer_generator import AnswerGenerator
    from cypher_builder import CypherBuilder
    from entity_linker import EntityLinker
    from graph_client import GraphClient
    from intent_planner import IntentPlanner
    from llm_client import LLMClient


LLM_DEBUG_QUESTIONS = [
    # 这些问题覆盖属性查询、关系正查、关系反查、多实体和兜底场景。
    # query_property
    "糖尿病是什么？",
    "为什么会得高血压？",
    "怎么预防高血压？",
    "感冒多久能好？",
    "糖尿病怎么治疗？",
    "高血压能治好吗？",
    "什么人容易得糖尿病？",

    # query_relation outgoing
    "乳腺癌的症状有哪些？",
    "糖尿病有哪些并发症？",
    "高血压不能吃什么？",
    "高血压适合吃什么？",
    "感冒要吃什么药？",
    "脑膜炎需要做什么检查？",

    # query_relation incoming
    "流鼻涕可能是什么病？",
    "哪些病人不能吃蜂蜜？",
    "鹅肉对什么病有好处？",
    "板蓝根颗粒能治什么病？",
    "血常规能查出什么病？",

    # multi-entity / boundary cases
    "板蓝根颗粒能不能治疗感冒？",
    "流鼻涕是不是感冒的症状？",
    "我最近身体不太舒服怎么办？",
    "糖尿病",
    "流鼻涕",
]


class LLMChatBotGraph:
    """LLM 版问答主入口。

    这条链路不复用 rule_based 的 question_parser / answer_search。
    它自己完成：实体对齐 -> 查询计划 -> Cypher -> Neo4j -> 答案生成。
    """

    def __init__(self):
        # debug=True 时打印每一步关键变量，适合断点调试和学习流程。
        self.debug = True
        self.llm_client = LLMClient()
        self.entity_linker = EntityLinker()
        self.intent_planner = IntentPlanner(self.llm_client)
        self.cypher_builder = CypherBuilder()
        # Neo4j 连接懒加载，避免只调试实体识别/查询计划时就要求数据库可用。
        self.graph_client = None
        self.answer_generator = AnswerGenerator(self.llm_client)

    def chat_main(self, sent, history=None):
        answer = "当前知识图谱中没有查到相关信息。"
        # 第一步：从 dict/ 词典中识别用户问题里的图谱实体。
        linked_entities = self.entity_linker.link(sent)
        self.debug_print("linked_entities", linked_entities)
        if not linked_entities:
            return answer

        # 第二步：让 LLM 基于实体和 schema 生成结构化查询计划。
        plan = self.intent_planner.plan(sent, linked_entities, history=history)
        self.debug_print("query_plan", plan)
        if not plan:
            return answer

        # 第三步：校验计划里的 subject 确实来自词典，避免 LLM 新增实体。
        subject = plan.get("subject", {})
        if not self.entity_linker.validate_entity(subject.get("name", ""), subject.get("label", "")):
            return answer

        # 第四步：把查询计划转换为参数化 Cypher。
        cypher, parameters = self.cypher_builder.build(plan)
        self.debug_print("cypher", cypher)
        self.debug_print("parameters", parameters)
        # 第五步：执行 Neo4j 查询。
        graph_results = self.get_graph_client().run(cypher, parameters)
        self.debug_print("graph_results", graph_results)
        # 第六步：基于图谱结果生成最终回答。
        answer = self.answer_generator.generate(sent, plan, graph_results, history=history)
        if self.llm_client.last_error:
            self.debug_print("llm_last_error", self.llm_client.last_error)
        return answer

    def get_graph_client(self):
        # 第一次真正查询图谱时才连接 Neo4j。
        if self.graph_client is None:
            self.graph_client = GraphClient()
        return self.graph_client

    def debug_print(self, name, value):
        # 集中控制调试输出，后续关闭只需要 self.debug = False。
        if self.debug:
            print("[LLMChatBotGraph] {0}: {1}".format(name, value))


def run_debug_questions(handler, questions):
    """批量运行调试问题，覆盖 LLM 通道的主要分支。"""
    for question in questions:
        print("用户:", question)
        answer = handler.chat_main(question)
        print("小勇:", answer)
        print("*" * 80)


if __name__ == "__main__":
    handler = LLMChatBotGraph()
    run_debug_questions(handler, LLM_DEBUG_QUESTIONS)

    # print("进入交互模式，输入 q / quit / exit 退出。")
    # while True:
    #     question = input("用户:").strip()
    #     if question in {"q", "quit", "exit"}:
    #         break
    #     print("小勇:", handler.chat_main(question))

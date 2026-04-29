#!/usr/bin/env python3
# coding: utf-8
# File: chatbot_graph.py
# Author: lhy<lhy_in_blcu@126.com,https://huangyong.github.io>
# Date: 18-10-4

try:
    from rule_based.question_classifier import *
    from rule_based.question_parser import *
    from rule_based.answer_search import *
    from llm_based.config import APP_DEBUG
    from llm_based.runtime import get_logger
except ModuleNotFoundError:
    from question_classifier import *
    from question_parser import *
    from answer_search import *
    from config import APP_DEBUG
    from runtime import get_logger

DEBUG_QUESTIONS = [
    # disease_symptom: 疾病 -> 症状
    "乳腺癌的症状有哪些？",
    # symptom_disease: 症状 -> 疾病
    "最近老是流鼻涕，可能是什么病？",
    # disease_cause: 疾病 -> 病因
    "为什么会得高血压？",
    # disease_acompany: 疾病 -> 并发症
    "糖尿病有哪些并发症？",
    # disease_not_food: 疾病 -> 忌口食物
    "高血压不能吃什么？",
    # disease_do_food: 疾病 -> 推荐食物/食谱
    "高血压适合吃什么食物？",
    # food_not_disease: 食物 -> 不适合哪些疾病
    "哪些病人不能吃蜂蜜？",
    # food_do_disease: 食物 -> 适合哪些疾病
    "鹅肉对什么病有好处？",
    # disease_drug: 疾病 -> 药品
    "感冒要吃什么药？",
    # drug_disease: 药品 -> 疾病
    "板蓝根颗粒能治什么病？",
    # disease_check: 疾病 -> 检查项目
    "脑膜炎需要做什么检查？",
    # check_disease: 检查项目 -> 疾病
    "血常规能查出什么病？",
    # disease_prevent: 疾病 -> 预防措施
    "怎么预防高血压？",
    # disease_lasttime: 疾病 -> 治疗周期
    "感冒多久能好？",
    # disease_cureway: 疾病 -> 治疗方式
    "糖尿病怎么治疗？",
    # disease_cureprob: 疾病 -> 治愈概率
    "高血压能治好吗？",
    # disease_easyget: 疾病 -> 易感人群
    "什么人容易得糖尿病？",
    # disease_desc: 疾病描述兜底
    "糖尿病",
]

DEBUG_MULTI_INTENT_QUESTIONS = [
    "高血压有什么症状，怎么治疗？",
    "糖尿病吃什么药，不能吃什么？",
    "感冒多久能好，怎么预防？",
    "脑膜炎有什么症状，需要做什么检查？",
]


'''问答类'''
class ChatBotGraph:
    def __init__(self):
        self.debug = APP_DEBUG
        self.logger = get_logger("rule_chatbot_graph")
        self.classifier = QuestionClassifier()
        self.parser = QuestionPaser()
        self.searcher = AnswerSearcher()

    def chat_main(self, sent):
        answer = '您好，我是小勇医药智能助理，希望可以帮到您。如果没答上来，可联系https://liuhuanyong.github.io/。祝您身体棒棒！'
        self.debug_print('question', sent)
        res_classify = self.classifier.classify(sent)
        self.debug_print('classify_result', res_classify)
        if not res_classify:
            self.debug_print('fallback_reason', 'QuestionClassifier did not match any medical entity.')
            return answer
        res_sql = self.parser.parser_main(res_classify)
        self.debug_print('parsed_sql', res_sql)
        final_answers = self.searcher.search_main(res_sql)
        self.debug_print('final_answers', final_answers)
        if not final_answers:
            self.debug_print('fallback_reason', 'Neo4j returned no usable answer.')
            return answer
        else:
            return '\n'.join(final_answers)

    def debug_print(self, name, value):
        if self.debug:
            self.logger.info('%s: %s', name, value)


def run_debug_questions(handler, questions):
    for question in questions:
        print('用户:', question)
        answer = handler.chat_main(question)
        print('小勇:', answer)
        print('*' * 80)


if __name__ == '__main__':
    handler = ChatBotGraph()

    run_debug_questions(handler, DEBUG_QUESTIONS)

    print('多意图问题调试:')
    print('*' * 80)
    run_debug_questions(handler, DEBUG_MULTI_INTENT_QUESTIONS)

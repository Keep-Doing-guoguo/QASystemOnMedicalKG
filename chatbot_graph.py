#!/usr/bin/env python3
# coding: utf-8
# File: chatbot_graph.py


from question_classifier import *
from question_parser import *
from answer_search import *

'''问答类'''
class ChatBotGraph:
    def __init__(self):
        self.classifier = QuestionClassifier()
        self.parser = QuestionPaser()
        self.searcher = AnswerSearcher()

    def chat_main(self, sent):
        answer = '您好，我是小勇医药智能助理，希望可以帮到您。如果没答上来，可联系https://liuhuanyong.github.io/。祝您身体棒棒！'
        res_classify = self.classifier.classify(sent)#问题分类；
        if not res_classify:
            return answer
        res_sql = self.parser.parser_main(res_classify)#这里是cpther语句给出
        final_answers = self.searcher.search_main(res_sql)#最后查询到答案
        if not final_answers:
            return answer
        else:
            return '\n'.join(final_answers)

if __name__ == '__main__':
    handler = ChatBotGraph()
    question = "乳腺癌的症状有哪些？"
    #question = "最近老流鼻涕怎么办？"
    answer = handler.chat_main(question)
    print('小勇:', answer)
    # while 1:
    #     question = input('用户:')
    #     answer = handler.chat_main(question)
    #     print('小勇:', answer)


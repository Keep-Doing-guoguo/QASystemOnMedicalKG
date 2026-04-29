import unittest

from llm_based.question_rewriter import QuestionRewriter


class DummyLLMClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def chat_text(self, system_prompt, user_payload):
        self.calls += 1
        return self.answer


class QuestionRewriterTests(unittest.TestCase):
    def test_complete_question_not_rewritten(self):
        llm = DummyLLMClient("不应被调用")
        rewriter = QuestionRewriter(llm)
        question = "高血压怎么治疗？"
        self.assertEqual(rewriter.rewrite(question, []), question)
        self.assertEqual(llm.calls, 0)

    def test_pronoun_question_is_rewritten(self):
        llm = DummyLLMClient("高血压的病因是什么？")
        rewriter = QuestionRewriter(llm)
        history = [
            {"role": "user", "question": "高血压是什么？"},
            {"role": "assistant", "answer": "高血压是一种常见疾病。"},
        ]
        rewritten = rewriter.rewrite("它的病因呢？", history)
        self.assertEqual(rewritten, "高血压的病因是什么？")


if __name__ == "__main__":
    unittest.main()

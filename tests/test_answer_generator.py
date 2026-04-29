import unittest

from llm_based.answer_generator import AnswerGenerator


class DummyLLMClient:
    def __init__(self):
        self.calls = 0

    def chat_text(self, system_prompt, user_payload):
        self.calls += 1
        return ""


class AnswerGeneratorTests(unittest.TestCase):
    def test_long_desc_uses_template_without_llm(self):
        llm = DummyLLMClient()
        generator = AnswerGenerator(llm)
        plan = {
            "action": "query_property",
            "subject": {"name": "糖尿病", "label": "Disease"},
            "property": "desc",
        }
        graph_results = [{"value": "很长的简介" * 80}]
        answer = generator.generate("糖尿病是什么？", plan, graph_results)
        self.assertIn("糖尿病的疾病简介", answer)
        self.assertEqual(llm.calls, 0)

    def test_truncate_graph_results(self):
        llm = DummyLLMClient()
        generator = AnswerGenerator(llm)
        data = [{"value": "a" * 500}]
        truncated = generator._truncate_graph_results(data, value_limit=100)
        self.assertTrue(truncated[0]["value"].endswith("..."))
        self.assertLessEqual(len(truncated[0]["value"]), 103)


if __name__ == "__main__":
    unittest.main()

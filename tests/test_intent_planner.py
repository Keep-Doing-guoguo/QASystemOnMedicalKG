import unittest

from llm_based.intent_planner import IntentPlanner


class DummyLLMClient:
    def __init__(self, result):
        self.result = result

    def chat_json(self, system_prompt, user_payload):
        return self.result


class IntentPlannerTests(unittest.TestCase):
    def test_normalize_valid_property_plan(self):
        llm = DummyLLMClient({
            "action": "query_property",
            "subject": {"name": "高血压", "label": "Disease"},
            "property": "cause",
        })
        planner = IntentPlanner(llm)
        plan = planner.plan("为什么会得高血压？", [{"name": "高血压", "labels": ["Disease"]}])
        self.assertEqual(plan["action"], "query_property")
        self.assertEqual(plan["property"], "cause")

    def test_invalid_relation_falls_back(self):
        llm = DummyLLMClient({
            "action": "query_relation",
            "subject": {"name": "流鼻涕", "label": "Symptom"},
            "relation": "bad_relation",
            "direction": "incoming",
        })
        planner = IntentPlanner(llm)
        plan = planner.plan("流鼻涕可能是什么病？", [{"name": "流鼻涕", "labels": ["Symptom"]}])
        self.assertEqual(plan["relation"], "has_symptom")


if __name__ == "__main__":
    unittest.main()

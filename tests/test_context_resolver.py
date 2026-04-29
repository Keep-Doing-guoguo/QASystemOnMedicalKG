import unittest

from llm_based.context_resolver import ContextResolver


class ContextResolverTests(unittest.TestCase):
    def test_followup_uses_current_topic(self):
        resolver = ContextResolver()
        history = [
            {
                "role": "assistant",
                "plan": {"subject": {"name": "高血压", "label": "Disease"}},
                "result_entities": [],
            }
        ]
        result = resolver.resolve("它的病因呢？", [], history)
        self.assertEqual(result["resolved_entities"][0]["name"], "高血压")
        self.assertEqual(result["intent_hint"]["target"], "cause")

    def test_ordinal_reference_uses_recent_results(self):
        resolver = ContextResolver()
        history = [
            {
                "role": "assistant",
                "plan": {"subject": {"name": "感冒", "label": "Disease"}},
                "result_entities": [
                    {"name": "板蓝根颗粒", "label": "Drug"},
                    {"name": "阿莫西林", "label": "Drug"},
                ],
            }
        ]
        result = resolver.resolve("第二个药还能治什么病？", [], history)
        self.assertEqual(result["referenced_result"]["name"], "阿莫西林")


if __name__ == "__main__":
    unittest.main()

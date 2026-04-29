import unittest

from llm_based.cypher_builder import CypherBuilder


class CypherBuilderTests(unittest.TestCase):
    def test_build_relation_chain_query(self):
        builder = CypherBuilder()
        plan = {
            "action": "query_relation_chain",
            "subject": {"name": "流鼻涕", "label": "Symptom"},
            "chain_template": "symptom_to_drug",
            "steps": [
                {"relation": "has_symptom", "direction": "incoming"},
                {"relation": "common_drug", "direction": "outgoing"},
            ],
        }
        cypher, parameters = builder.build(plan)
        self.assertIn("MATCH", cypher)
        self.assertIn("has_symptom", cypher)
        self.assertIn("common_drug", cypher)
        self.assertEqual(parameters["subject_name"], "流鼻涕")


if __name__ == "__main__":
    unittest.main()

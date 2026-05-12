import unittest

from llm_based.session_store import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_create_and_append_history(self):
        store = SessionStore(llm_client=None, db_path=":memory:")
        session_id = store.create_session()
        store.add_turn(session_id, "user", question="高血压不能吃什么？")
        store.add_turn(session_id, "assistant", answer="请避免高盐食物。")
        session = store.get_session(session_id)
        self.assertEqual(session["session_id"], session_id)
        self.assertEqual(len(session["history"]), 2)

    def test_create_with_external_session_id(self):
        store = SessionStore(llm_client=None, db_path=":memory:")
        session_id = store.create_session("debug-memory-002")
        self.assertEqual(session_id, "debug-memory-002")
        self.assertIsNotNone(store.get_session("debug-memory-002"))

    def test_get_history_returns_summary_and_recent_turns(self):
        store = SessionStore(llm_client=None, db_path=":memory:")
        session_id = store.create_session("history-test")
        store._db.save_summary(session_id, "用户此前咨询了高血压忌口。")
        store.add_turn(session_id, "user", question="问题1")
        store.add_turn(session_id, "assistant", answer="回答1")
        store.add_turn(session_id, "user", question="问题2")

        history = store.get_history(session_id, max_turns=2)

        self.assertEqual(history[0], {
            "role": "summary",
            "content": "用户此前咨询了高血压忌口。",
        })
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["answer"], "回答1")
        self.assertEqual(history[2]["role"], "user")
        self.assertEqual(history[2]["question"], "问题2")

    def test_build_memory_context_from_assistant_turns(self):
        store = SessionStore(llm_client=None, db_path=":memory:")
        history = [
            {"role": "user", "question": "高血压不能吃什么？"},
            {
                "role": "assistant",
                "answer": "高血压患者应避免鸡肝。",
                "plan": {
                    "action": "query_relation",
                    "subject": {"name": "高血压", "label": "Disease"},
                    "relation": "no_eat",
                    "direction": "outgoing",
                },
                "result_entities": [
                    {"name": "鸡肝", "label": "Entity"},
                    {"name": "咸鸭蛋", "label": "Entity"},
                ],
                "graph_results": [
                    {
                        "subject": "高血压",
                        "relation": "no_eat",
                        "relation_name": "忌吃",
                        "object": "鸡肝",
                    }
                ],
            },
        ]

        memory_context = store.build_memory_context(history)

        self.assertEqual(memory_context["current_topic"], {
            "name": "高血压",
            "label": "Disease",
        })
        self.assertEqual(memory_context["last_query_plan"]["relation"], "no_eat")
        self.assertEqual(memory_context["recent_result_entities"][0]["name"], "鸡肝")
        self.assertEqual(memory_context["recent_graph_results"][0]["object"], "鸡肝")


if __name__ == "__main__":
    unittest.main()

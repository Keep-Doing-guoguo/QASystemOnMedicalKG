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


if __name__ == "__main__":
    unittest.main()

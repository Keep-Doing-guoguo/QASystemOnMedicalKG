import unittest

from llm_based.memory_compressor import MemoryCompressor
from llm_based.session_store import SessionStore


class DummyLLMClient:
    def chat_text(self, system_prompt, user_payload):
        return "用户此前咨询了：1. 感冒的症状；2. 高血压的病因"


class MemoryCompressorTests(unittest.TestCase):
    def test_fallback_compress(self):
        turns = [
            {"role": "user", "question": "感冒的症状是什么？"},
            {"role": "assistant", "answer": "流鼻涕、咳嗽。"},
            {"role": "user", "question": "高血压的病因呢？"},
        ]
        summary = MemoryCompressor._fallback_compress(turns, "")
        self.assertIn("感冒的症状是什么？", summary)
        self.assertIn("高血压的病因呢？", summary)

    def test_session_store_compresses_old_turns(self):
        store = SessionStore(llm_client=DummyLLMClient(), db_path=":memory:")
        session_id = store.create_session()
        for index in range(12):
            store.add_turn(session_id, "user", question=f"问题{index}")
        history = store.get_history(session_id)
        self.assertTrue(any(turn.get("role") == "summary" for turn in history))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/7 19:59
@source from: 
"""
from llm_base.memory_compressor import MemoryCompressor
from llm_base.session_store import SessionStore



class DummyLLMClient:
    def chat_text(self, system_prompt, user_payload):
        return "用户此前咨询了：1. 感冒的症状；2. 高血压的病因"

a = MemoryCompressor(DummyLLMClient())

turns = [
            {"role": "user", "question": "感冒的症状是什么？"},
            {"role": "assistant", "answer": "流鼻涕、咳嗽。"},
            {"role": "user", "question": "高血压的病因呢？"},
        ]
#summary = a._fallback_compress(turns, "")
store = SessionStore(llm_client=DummyLLMClient(),db_path="/Users/zhangguowen/PROJECT/模仿- QA/data/sessions.db")
session_id = store.create_session()
for index in range(20):
    store.add_turn(session_id, "user", question=f"问题{index}")
history = store.get_history(session_id)



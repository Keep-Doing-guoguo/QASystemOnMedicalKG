#!/usr/bin/env python3
# coding: utf-8

import threading
import time
import uuid

from llm_based.memory_compressor import MemoryCompressor
from llm_based.persistent_store import PersistentStore


class SessionStore:
    """会话存储：内存缓存 + SQLite 持久化 + LLM 摘要压缩。

    - 内存中只缓存最近 N 轮完整对话（快速读取）
    - 每次 add_turn 同步写入 SQLite（持久化）
    - 轮次超过阈值时触发 LLM 压缩（节省 token）
    - session 不设 TTL，长期保存
    """

    # 内存保留的最近轮次上限
    RECENT_TURNS = 6
    # 触发压缩的轮次阈值
    COMPRESS_THRESHOLD = 10

    def __init__(self, llm_client=None, db_path=None):
        self._db = PersistentStore(db_path=db_path)
        self._compressor = MemoryCompressor(llm_client) if llm_client else None
        self._memory = {}  # session_id -> list of recent turns
        self._lock = threading.Lock()

        # 守护线程定期清理超长期未活动的 session
        cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleaner.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_session(self):
        """创建新 session，返回 session_id。"""
        session_id = str(uuid.uuid4())
        self._db.create_session(session_id)
        with self._lock:
            self._memory[session_id] = []
        return session_id

    def get_session(self, session_id):
        """按 id 获取 session。不存在返回 None。"""
        if not self._db.session_exists(session_id):
            return None
        self._db.touch_session(session_id)

        # 确保内存中有缓存
        with self._lock:
            if session_id not in self._memory:
                recent = self._db.get_recent_turns(session_id, self.RECENT_TURNS)
                self._memory[session_id] = recent

        history = self.get_history(session_id)
        return {
            "session_id": session_id,
            "history": history,
            "memory_context": self.build_memory_context(history),
        }

    def add_turn(self, session_id, role, **kwargs):
        """向 session 追加一轮对话，同步写入 SQLite。"""
        turn = {"role": role}
        turn.update(kwargs)

        # 写入 SQLite
        self._db.add_turn(session_id, role, **kwargs)

        # 更新内存缓存
        with self._lock:
            if session_id not in self._memory:
                self._memory[session_id] = []
            self._memory[session_id].append(turn)
            # 内存只保留最近 N 轮
            if len(self._memory[session_id]) > self.RECENT_TURNS * 2:
                self._memory[session_id] = self._memory[session_id][-self.RECENT_TURNS:]

        # 检查是否需要压缩
        self._maybe_compress(session_id)

    def get_history(self, session_id, max_turns=None):
        """获取对话历史：[摘要] + [最近完整轮次]。"""
        result = []

        # 加入摘要（如果有）
        summary = self._db.get_summary(session_id)
        if summary:
            result.append({"role": "summary", "content": summary})

        # 加入最近轮次
        with self._lock:
            recent = self._memory.get(session_id)
        if recent is None:
            recent = self._db.get_recent_turns(session_id, self.RECENT_TURNS)

        if max_turns is not None:
            recent = recent[-max_turns:]
        result.extend(recent)
        return result

    def clear_session(self, session_id):
        """清除指定 session。"""
        self._db.clear_session(session_id)
        with self._lock:
            self._memory.pop(session_id, None)

    def session_count(self):
        """返回 session 总数。"""
        return self._db.session_count()

    def build_memory_context(self, history):
        current_topic = None
        last_query_plan = {}
        recent_result_entities = []
        recent_graph_results = []
        for turn in reversed(history or []):
            if turn.get("role") != "assistant":
                continue
            plan = turn.get("plan") or {}
            if not last_query_plan and plan:
                last_query_plan = plan
            subject = plan.get("subject") or {}
            if not current_topic and subject.get("name") and subject.get("label"):
                current_topic = {"name": subject["name"], "label": subject["label"]}
            if not recent_result_entities and turn.get("result_entities"):
                recent_result_entities = turn.get("result_entities", [])
            if not recent_graph_results and turn.get("graph_results"):
                recent_graph_results = turn.get("graph_results", [])
            if current_topic and last_query_plan and recent_result_entities:
                break
        return {
            "current_topic": current_topic,
            "last_query_plan": last_query_plan,
            "recent_result_entities": recent_result_entities[:8],
            "recent_graph_results": recent_graph_results[:8],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_compress(self, session_id):
        """轮次超过阈值时触发压缩。"""
        if not self._compressor:
            return

        total = self._db.get_turn_count(session_id)
        if total < self.COMPRESS_THRESHOLD:
            return

        # 计算要压缩的轮次数：保留最近 RECENT_TURNS 条，其余压缩
        compress_count = total - self.RECENT_TURNS
        if compress_count <= 0:
            return

        # 获取要压缩的旧轮次的边界 id
        boundary_id = self._db.get_oldest_turn_id(session_id, offset=self.RECENT_TURNS)
        if boundary_id is None:
            return

        # 取出旧轮次
        old_rows = self._db.get_turns_before(session_id, before_id=boundary_id)
        if not old_rows:
            return

        old_turns = []
        for tid, role, question, answer in old_rows:
            turn = {"role": role}
            if question:
                turn["question"] = question
            if answer:
                turn["answer"] = answer
            old_turns.append(turn)

        # 获取已有摘要
        existing_summary = self._db.get_summary(session_id)

        # 调用 LLM 压缩
        new_summary = self._compressor.compress(old_turns, existing_summary)

        # 保存新摘要并删除已压缩的旧轮次
        if new_summary:
            self._db.save_summary(session_id, new_summary)
            self._db.delete_turns_before(session_id, boundary_id)

    def _cleanup_loop(self):
        """每小时清理超过 30 天未活动的 session。"""
        while True:
            time.sleep(3600)
            try:
                self._db.cleanup_stale(max_age_days=30)
            except Exception:
                pass

#!/usr/bin/env python3
# coding: utf-8

import json
import os
import sqlite3
import threading
import time


class PersistentStore:
    """SQLite 持久化会话存储。

    使用 WAL 模式 + 线程本地连接，兼容 ThreadingHTTPServer。
    每个线程持有自己的 sqlite3 连接，避免跨线程共享连接的问题。
    """

    def __init__(self, db_path=None):
        if db_path is None:
            db_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(db_dir, "data", "sessions.db")
        db_parent = os.path.dirname(db_path)
        if db_path != ":memory:" and db_parent:
            os.makedirs(db_parent, exist_ok=True)

        self._db_path = db_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._ensure_table()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_session(self, session_id):
        """创建新 session 记录。"""
        now = time.time()
        conn = self._conn()
        conn.execute(
            "INSERT INTO sessions (session_id, created_at, last_active, summary) VALUES (?, ?, ?, ?)",
            (session_id, now, now, ""),
        )
        conn.commit()

    def session_exists(self, session_id):
        """检查 session 是否存在。"""
        row = self._conn().execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row is not None

    def touch_session(self, session_id):
        """更新 session 的 last_active 时间戳。"""
        conn = self._conn()
        conn.execute(
            "UPDATE sessions SET last_active = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        conn.commit()

    def add_turn(self, session_id, role, **kwargs):
        """向 session 追加一轮对话。"""
        conn = self._conn()
        conn.execute(
            "INSERT INTO turns (session_id, role, question, answer, entities, plan, result_entities, graph_results, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                role,
                kwargs.get("question", ""),
                kwargs.get("answer", ""),
                json.dumps(kwargs.get("entities", []), ensure_ascii=False),
                json.dumps(kwargs.get("plan", {}), ensure_ascii=False),
                json.dumps(kwargs.get("result_entities", []), ensure_ascii=False),
                json.dumps(kwargs.get("graph_results", []), ensure_ascii=False),
                time.time(),
            ),
        )
        conn.execute(
            "UPDATE sessions SET last_active = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        conn.commit()

    def get_recent_turns(self, session_id, limit=6):
        """获取最近 N 轮对话（按 id 倒序取再反转）。"""
        rows = self._conn().execute(
            "SELECT role, question, answer, entities, plan, result_entities, graph_results FROM turns "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        result = []
        for role, question, answer, entities, plan, result_entities, graph_results in reversed(rows):
            turn = {"role": role}
            if question:
                turn["question"] = question
            if answer:
                turn["answer"] = answer
            if entities:
                try:
                    turn["entities"] = json.loads(entities)
                except (json.JSONDecodeError, TypeError):
                    pass
            if plan:
                try:
                    turn["plan"] = json.loads(plan)
                except (json.JSONDecodeError, TypeError):
                    pass
            if result_entities:
                try:
                    turn["result_entities"] = json.loads(result_entities)
                except (json.JSONDecodeError, TypeError):
                    pass
            if graph_results:
                try:
                    turn["graph_results"] = json.loads(graph_results)
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(turn)
        return result

    def get_turns_before(self, session_id, before_id=None, limit=100):
        """获取指定 id 之前的旧轮次（用于压缩）。"""
        if before_id is None:
            rows = self._conn().execute(
                "SELECT id, role, question, answer FROM turns "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = self._conn().execute(
                "SELECT id, role, question, answer FROM turns "
                "WHERE session_id = ? AND id < ? ORDER BY id ASC",
                (session_id, before_id),
            ).fetchall()
        return rows

    def get_turn_count(self, session_id):
        """获取 session 的总轮次数。"""
        row = self._conn().execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row[0] if row else 0

    def get_oldest_turn_id(self, session_id, offset=0):
        """获取第 offset+1 条旧轮次的 id（用于确定压缩边界）。"""
        row = self._conn().execute(
            "SELECT id FROM turns WHERE session_id = ? ORDER BY id ASC LIMIT 1 OFFSET ?",
            (session_id, offset),
        ).fetchone()
        return row[0] if row else None

    def delete_turns_before(self, session_id, before_id):
        """删除指定 id 之前的轮次（压缩后清理）。"""
        conn = self._conn()
        conn.execute(
            "DELETE FROM turns WHERE session_id = ? AND id < ?",
            (session_id, before_id),
        )
        conn.commit()

    def get_summary(self, session_id):
        """获取 session 的压缩摘要。"""
        row = self._conn().execute(
            "SELECT summary FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row[0] if row else ""

    def save_summary(self, session_id, summary):
        """保存压缩摘要。"""
        conn = self._conn()
        conn.execute(
            "UPDATE sessions SET summary = ? WHERE session_id = ?",
            (summary, session_id),
        )
        conn.commit()

    def clear_session(self, session_id):
        """清除指定 session 的所有数据。"""
        conn = self._conn()
        conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()

    def cleanup_stale(self, max_age_days=30):
        """清理超过 max_age_days 天未活动的 session。"""
        cutoff = time.time() - max_age_days * 86400
        conn = self._conn()
        stale_ids = [
            row[0]
            for row in conn.execute(
                "SELECT session_id FROM sessions WHERE last_active < ?", (cutoff,)
            ).fetchall()
        ]
        for sid in stale_ids:
            conn.execute("DELETE FROM turns WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
        conn.commit()
        return len(stale_ids)

    def session_count(self):
        """返回 session 总数。"""
        row = self._conn().execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _conn(self):
        """获取当前线程的 SQLite 连接。"""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return conn

    def _ensure_table(self):
        """首次启动时建表。"""
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                last_active REAL NOT NULL,
                summary TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                question TEXT DEFAULT '',
                answer TEXT DEFAULT '',
                entities TEXT DEFAULT '[]',
                plan TEXT DEFAULT '{}',
                result_entities TEXT DEFAULT '[]',
                graph_results TEXT DEFAULT '[]',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_turns_session
                ON turns(session_id, id);
        """)
        existing = [row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()]
        if "result_entities" not in existing:
            conn.execute("ALTER TABLE turns ADD COLUMN result_entities TEXT DEFAULT '[]'")
        if "graph_results" not in existing:
            conn.execute("ALTER TABLE turns ADD COLUMN graph_results TEXT DEFAULT '[]'")
        conn.commit()

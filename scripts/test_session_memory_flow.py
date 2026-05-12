#!/usr/bin/env python3
# coding: utf-8

"""
Manual test script for SessionStore memory flow.

Usage:
  python scripts/test_session_memory_flow.py
  python scripts/test_session_memory_flow.py --db data/sessions.db --session-id debug-memory-002
  python scripts/test_session_memory_flow.py --memory
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT_DIR / "data" / "sessions.db"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_based.session_store import SessionStore


def create_store(db_path, use_memory):
    """Create SessionStore for local SQLite file or in-memory SQLite."""
    if use_memory:
        return SessionStore(llm_client=None, db_path=":memory:")
    return SessionStore(llm_client=None, db_path=str(db_path))


def create_or_load_session(store, session_id=""):
    """Create a session with a fixed id, or load it if it already exists."""
    if session_id:
        existing = store.get_session(session_id)
        if existing:
            return session_id
        return store.create_session(session_id)
    return store.create_session()


def add_sample_turns(store, session_id):
    """Write one user turn and one assistant turn with memory metadata."""
    store.add_turn(session_id, "user", question="高血压不能吃什么？")
    store.add_turn(
        session_id,
        "assistant",
        answer="请避免高盐食物。",
        entities=[
            {"name": "高血压", "types": ["disease"], "labels": ["Disease"]},
        ],
        plan={
            "action": "query_relation",
            "subject": {"name": "高血压", "label": "Disease"},
            "relation": "no_eat",
            "direction": "outgoing",
        },
        result_entities=[
            {"name": "咸鸭蛋", "label": "Entity"},
            {"name": "鸡肝", "label": "Entity"},
        ],
        graph_results=[
            {
                "subject": "高血压",
                "relation": "no_eat",
                "relation_name": "忌吃",
                "object": "咸鸭蛋",
            }
        ],
    )


def print_session(store, session_id):
    """Print get_session result, including history and memory_context."""
    session = store.get_session(session_id)
    print_title("get_session")
    print_json(session)


def print_history(store, session_id, max_turns=None):
    """Print get_history result."""
    history = store.get_history(session_id, max_turns=max_turns)
    title = "get_history"
    if max_turns is not None:
        title += "(max_turns={0})".format(max_turns)
    print_title(title)
    print_json(history)


def print_memory_context(store, session_id):
    """Build and print memory_context from current history."""
    history = store.get_history(session_id)
    memory_context = store.build_memory_context(history)
    print_title("build_memory_context")
    print_json(memory_context)


def run_flow(args):
    db_path = Path(args.db).expanduser().resolve()
    store = create_store(db_path, args.memory)
    session_id = create_or_load_session(store, args.session_id)

    if args.add_sample:
        add_sample_turns(store, session_id)

    print_title("basic")
    print("db_path: {0}".format(":memory:" if args.memory else db_path))
    print("session_id: {0}".format(session_id))

    print_session(store, session_id)
    print_history(store, session_id)
    print_history(store, session_id, max_turns=2)
    print_memory_context(store, session_id)


def parse_args():
    parser = argparse.ArgumentParser(description="Test SessionStore memory functions.")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="SQLite db path. Default: data/sessions.db",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Use in-memory SQLite. Data will not be written to disk.",
    )
    parser.add_argument(
        "--session-id",
        default="debug-memory-002",
        help="Session id to create or load. Default: debug-memory-002",
    )
    parser.add_argument(
        "--add-sample",
        action="store_true",
        default=True,
        help="Add sample turns before reading memory. Default: true",
    )
    return parser.parse_args()


def print_title(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_flow(parse_args())

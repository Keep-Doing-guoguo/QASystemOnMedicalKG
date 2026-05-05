#!/usr/bin/env python3
# coding: utf-8

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT_DIR / "data" / "sessions.db"


def main():
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        raise SystemExit("DB file not found: {0}".format(db_path))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    if args.session_id:
        show_session(conn, args.session_id, args.limit)
    else:
        list_sessions(conn, args.limit)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Inspect local KG QA session memory stored in SQLite."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="SQLite db path. Default: data/sessions.db",
    )
    parser.add_argument(
        "--session-id",
        help="Show details for one session id.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max sessions or turns to print. Default: 20",
    )
    return parser.parse_args()


def list_sessions(conn, limit):
    rows = conn.execute(
        """
        SELECT
            s.session_id,
            s.created_at,
            s.last_active,
            LENGTH(COALESCE(s.summary, '')) AS summary_len,
            COUNT(t.id) AS turn_count
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        GROUP BY s.session_id
        ORDER BY s.last_active DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    if not rows:
        print("No sessions found.")
        return

    print("sessions:")
    for row in rows:
        print(
            "- session_id={0} turns={1} summary_len={2} created_at={3} last_active={4}".format(
                row["session_id"],
                row["turn_count"],
                row["summary_len"],
                fmt_time(row["created_at"]),
                fmt_time(row["last_active"]),
            )
        )


def show_session(conn, session_id, limit):
    session = conn.execute(
        "SELECT session_id, created_at, last_active, summary FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not session:
        print("Session not found: {0}".format(session_id))
        return

    print("session_id: {0}".format(session["session_id"]))
    print("created_at: {0}".format(fmt_time(session["created_at"])))
    print("last_active: {0}".format(fmt_time(session["last_active"])))
    print("summary: {0}".format(session["summary"] or "(empty)"))
    print()

    rows = conn.execute(
        """
        SELECT id, role, question, answer, entities, plan, result_entities, graph_results, created_at
        FROM turns
        WHERE session_id = ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()

    if not rows:
        print("No turns found.")
        return

    print("turns:")
    for row in rows:
        print("- id={0} role={1} created_at={2}".format(
            row["id"], row["role"], fmt_time(row["created_at"])
        ))
        if row["question"]:
            print("  question: {0}".format(row["question"]))
        if row["answer"]:
            print("  answer: {0}".format(shorten(row["answer"], 240)))
        print_json_field("entities", row["entities"])
        print_json_field("plan", row["plan"])
        print_json_field("result_entities", row["result_entities"])
        print_json_field("graph_results", row["graph_results"], max_items=3)


def print_json_field(name, raw, max_items=None):
    if not raw:
        return
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        print("  {0}: {1}".format(name, shorten(raw, 180)))
        return
    if value in ({}, [], None):
        return
    if isinstance(value, list) and max_items is not None:
        value = value[:max_items]
    print("  {0}: {1}".format(name, json.dumps(value, ensure_ascii=False)))


def fmt_time(value):
    if not value:
        return "-"
    return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")


def shorten(value, max_len):
    value = str(value).replace("\n", " ")
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


if __name__ == "__main__":
    main()
#python scripts/inspect_sessions_db.py --limit 5
#python scripts/inspect_sessions_db.py --session-id debug-memory-002
#python scripts/inspect_sessions_db.py --db data/sessions.db --session-id debug-memory-002

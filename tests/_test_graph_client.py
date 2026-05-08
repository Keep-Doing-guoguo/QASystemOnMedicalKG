#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 17:55
@source from: 
"""
#!/usr/bin/env python3
# coding: utf-8

"""
Run GraphClient cases manually without unittest.

Default mode does not connect to Neo4j. It injects a fake graph object to verify
GraphClient.run behavior.

Usage:
  python scripts/run_graph_client_cases.py
  python scripts/run_graph_client_cases.py --cypher "RETURN $name AS name" --params '{"name":"高血压"}'
  python scripts/run_graph_client_cases.py --live --cypher "RETURN 1 AS value"
  python scripts/run_graph_client_cases.py --live --cypher "MATCH (n:Disease) RETURN n.name AS name LIMIT 5"
"""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm_base.graph_client import GraphClient


class FakeResult:
    """Small stand-in for py2neo result object."""

    def __init__(self, rows):
        self.rows = rows

    def data(self):
        return self.rows


class FakeGraph:
    """Fake graph object that records the last query and returns fixed rows."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = 0
        self.last_cypher = ""
        self.last_parameters = {}

    def run(self, cypher, parameters=None):
        self.calls += 1
        self.last_cypher = cypher
        self.last_parameters = parameters or {}
        return FakeResult(self.rows)


def main():
    args = parse_args()
    if args.live:
        run_live(args)
        return
    if args.cypher:
        run_custom_mock(args)
        return
    run_builtin_cases()


def parse_args():
    parser = argparse.ArgumentParser(description="Manually run GraphClient cases.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use real Neo4j connection from llm_based.config.",
    )
    parser.add_argument(
        "--cypher",
        default="",
        help="Cypher to execute. In mock mode this is only recorded; in live mode it is executed.",
    )
    parser.add_argument(
        "--params",
        default="{}",
        help="JSON parameters for Cypher. Default: {}",
    )
    parser.add_argument(
        "--mock-rows",
        default='[{"name":"高血压"}]',
        help="JSON rows returned by fake graph in mock mode.",
    )
    return parser.parse_args()


def run_builtin_cases():
    cases = [
        empty_cypher_returns_empty_list,
        valid_cypher_passes_parameters_to_graph,
    ]

    passed = 0
    for case in cases:
        ok = run_case(case)
        if ok:
            passed += 1

    print()
    print("Result: {0}/{1} passed".format(passed, len(cases)))
    if passed != len(cases):
        raise SystemExit(1)


def run_case(case_func):
    print()
    print("=" * 80)
    print(case_func.__name__)
    print("=" * 80)
    try:
        data = case_func()
    except Exception as exc:
        print("FAIL:", exc)
        return False

    print("cypher:", data["cypher"])
    print("parameters:")
    print_json(data["parameters"])
    print("result:")
    print_json(data["result"])
    print("fake_graph_calls:", data["fake_graph_calls"])
    print("checks:")
    for item in data["checks"]:
        print("- {0}: {1}".format(item["name"], "PASS" if item["ok"] else "FAIL"))

    ok = all(item["ok"] for item in data["checks"])
    print("status:", "PASS" if ok else "FAIL")
    return ok


def run_custom_mock(args):
    cypher = args.cypher
    parameters = json.loads(args.params)
    rows = json.loads(args.mock_rows)
    client, fake_graph = fake_client(rows)
    result = client.run(cypher, parameters)

    print("mode: mock")
    print("cypher:", cypher)
    print("parameters:")
    print_json(parameters)
    print("result:")
    print_json(result)
    print("fake_graph_calls:", fake_graph.calls)
    print("fake_graph_last_cypher:", fake_graph.last_cypher)
    print("fake_graph_last_parameters:")
    print_json(fake_graph.last_parameters)


def run_live(args):
    cypher = args.cypher or "RETURN 1 AS value"
    parameters = json.loads(args.params)
    client = GraphClient()
    result = client.run(cypher, parameters)

    print("mode: live")
    print("cypher:", cypher)
    print("parameters:")
    print_json(parameters)
    print("result:")
    print_json(result)


def empty_cypher_returns_empty_list():
    client, fake_graph = fake_client([{"name": "不应返回"}])
    result = client.run("", {"name": "高血压"})
    return case_result(
        "",
        {"name": "高血压"},
        result,
        fake_graph.calls,
        [
            check("result is empty list", result == []),
            check("graph.run is not called", fake_graph.calls == 0),
        ],
    )


def valid_cypher_passes_parameters_to_graph():
    rows = [{"name": "高血压"}]
    client, fake_graph = fake_client(rows)
    cypher = "MATCH (n:Disease) WHERE n.name = $name RETURN n.name AS name"
    parameters = {"name": "高血压"}
    result = client.run(cypher, parameters)
    return case_result(
        cypher,
        parameters,
        result,
        fake_graph.calls,
        [
            check("result equals fake rows", result == rows),
            check("graph.run is called once", fake_graph.calls == 1),
            check("cypher is passed through", fake_graph.last_cypher == cypher),
            check("parameters are passed through", fake_graph.last_parameters == parameters),
        ],
    )


def fake_client(rows):
    """Build GraphClient without running its __init__, then inject fake graph."""
    client = GraphClient.__new__(GraphClient)
    client.debug = False
    client.logger = None
    fake_graph = FakeGraph(rows)
    client.g = fake_graph
    return client, fake_graph


def case_result(cypher, parameters, result, fake_graph_calls, checks):
    return {
        "cypher": cypher,
        "parameters": parameters,
        "result": result,
        "fake_graph_calls": fake_graph_calls,
        "checks": checks,
    }


def check(name, ok):
    return {"name": name, "ok": bool(ok)}


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

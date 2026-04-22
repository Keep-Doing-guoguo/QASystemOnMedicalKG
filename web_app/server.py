#!/usr/bin/env python3
# coding: utf-8

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from llm_based.answer_generator import AnswerGenerator
from llm_based.cypher_builder import CypherBuilder
from llm_based.entity_linker import EntityLinker
from llm_based.graph_client import GraphClient
from llm_based.intent_planner import IntentPlanner
from llm_based.llm_client import LLMClient
from rule_based.answer_search import AnswerSearcher
from rule_based.question_classifier import QuestionClassifier
from rule_based.question_parser import QuestionPaser


class RuleQAService:
    def __init__(self):
        self.classifier = QuestionClassifier()
        self.classifier.debug = False
        self.parser = QuestionPaser()
        self.searcher = None

    def chat(self, question):
        fallback = "当前知识图谱中没有查到相关信息。"
        searcher = self._searcher()
        res_classify = self.classifier.classify(question)
        if not res_classify:
            return self._empty_response(question, fallback)

        entity_types = []
        for types in res_classify.get("args", {}).values():
            entity_types += types

        sql_blocks = self.parser.parser_main(res_classify)
        graph_results = []
        cypher = []
        final_answers = []
        for sql_block in sql_blocks:
            question_type = sql_block["question_type"]
            answers = []
            for query in sql_block["sql"]:
                cypher.append(query)
                result = searcher.g.run(query).data()
                answers += result
                graph_results += result
            final_answer = searcher.answer_prettify(question_type, answers)
            if final_answer:
                final_answers.append(final_answer)

        answer = "\n".join(final_answers) if final_answers else fallback
        return {
            "mode": "rule_based",
            "question": question,
            "answer": answer,
            "debug": {
                "matched_entities": res_classify.get("args", {}),
                "entity_types": entity_types,
                "question_types": res_classify.get("question_types", []),
                "cypher": cypher,
                "graph_results": graph_results,
            },
            "graph": graph_from_rule_results(graph_results),
        }

    def _empty_response(self, question, answer):
        return {
            "mode": "rule_based",
            "question": question,
            "answer": answer,
            "debug": {
                "matched_entities": {},
                "entity_types": [],
                "question_types": [],
                "cypher": [],
                "graph_results": [],
            },
            "graph": {"nodes": [], "edges": []},
        }

    def _searcher(self):
        if self.searcher is None:
            self.searcher = AnswerSearcher()
        return self.searcher


class LLMQAService:
    def __init__(self):
        self.llm_client = LLMClient()
        self.entity_linker = EntityLinker()
        self.intent_planner = IntentPlanner(self.llm_client)
        self.cypher_builder = CypherBuilder()
        self.graph_client = None
        self.answer_generator = AnswerGenerator(self.llm_client)

    def chat(self, question):
        fallback = "当前知识图谱中没有查到相关信息。"
        linked_entities = self.entity_linker.link(question)
        if not linked_entities:
            return self._empty_response(question, fallback)

        plan = self.intent_planner.plan(question, linked_entities)
        if not plan:
            return self._empty_response(question, fallback, linked_entities=linked_entities)

        subject = plan.get("subject", {})
        if not self.entity_linker.validate_entity(subject.get("name", ""), subject.get("label", "")):
            return self._empty_response(question, fallback, linked_entities=linked_entities, query_plan=plan)

        cypher, parameters = self.cypher_builder.build(plan)
        graph_results = self._graph_client().run(cypher, parameters)
        answer = self.answer_generator.generate(question, plan, graph_results)
        return {
            "mode": "llm_based",
            "question": question,
            "answer": answer,
            "debug": {
                "linked_entities": linked_entities,
                "query_plan": plan,
                "cypher": cypher,
                "parameters": parameters,
                "graph_results": graph_results,
            },
            "graph": graph_from_llm_results(plan, graph_results),
        }

    def _empty_response(self, question, answer, linked_entities=None, query_plan=None):
        return {
            "mode": "llm_based",
            "question": question,
            "answer": answer,
            "debug": {
                "linked_entities": linked_entities or [],
                "query_plan": query_plan or {},
                "cypher": "",
                "parameters": {},
                "graph_results": [],
            },
            "graph": {"nodes": [], "edges": []},
        }

    def _graph_client(self):
        if self.graph_client is None:
            self.graph_client = GraphClient()
        return self.graph_client


def graph_from_rule_results(results):
    nodes = {}
    edges = []
    for item in results:
        start = item.get("m.name")
        end = item.get("n.name")
        rel_name = item.get("r.name") or item.get("relation_name") or "关系"
        rel_type = item.get("relation") or rel_name
        if not start or not end:
            continue
        nodes[start] = {"id": start, "label": start, "type": "Entity"}
        nodes[end] = {"id": end, "label": end, "type": "Entity"}
        edges.append({"source": start, "target": end, "label": rel_name, "type": rel_type})
    return {"nodes": list(nodes.values()), "edges": edges}


def graph_from_llm_results(plan, results):
    nodes = {}
    edges = []
    subject = plan.get("subject", {})
    subject_name = subject.get("name")
    subject_label = subject.get("label", "Entity")
    if subject_name:
        nodes[subject_name] = {"id": subject_name, "label": subject_name, "type": subject_label}

    if plan.get("action") == "query_relation":
        for item in results:
            target = item.get("object")
            if not target or not subject_name:
                continue
            relation_name = item.get("relation_name") or item.get("relation") or plan.get("relation", "关系")
            nodes[target] = {"id": target, "label": target, "type": "Entity"}
            if plan.get("direction") == "incoming":
                edges.append({"source": target, "target": subject_name, "label": relation_name, "type": item.get("relation", "")})
            else:
                edges.append({"source": subject_name, "target": target, "label": relation_name, "type": item.get("relation", "")})
    return {"nodes": list(nodes.values()), "edges": edges}


class AppHandler(SimpleHTTPRequestHandler):
    rule_service = None
    llm_service = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            self.write_json({"ok": True, "service": "Medical KG QA Studio"})
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            question = (payload.get("question") or "").strip()
            if not question:
                self.write_json({"error": "question is required"}, status=400)
                return

            if path == "/api/rule/chat":
                data = self.rule_service.chat(question)
            elif path == "/api/llm/chat":
                data = self.llm_service.chat(question)
            else:
                self.write_json({"error": "not found"}, status=404)
                return
            self.write_json(data)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=500)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def write_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8000"))
    AppHandler.rule_service = RuleQAService()
    AppHandler.llm_service = LLMQAService()
    server = ThreadingHTTPServer((host, port), AppHandler)
    print("Medical KG QA Studio: http://{0}:{1}".format(host, port))
    server.serve_forever()


if __name__ == "__main__":
    main()

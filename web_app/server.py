#!/usr/bin/env python3
# coding: utf-8

import json
import os
import sys
import logging
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from llm_based.answer_generator import AnswerGenerator
from llm_based.cypher_builder import CypherBuilder
from llm_based.context_resolver import ContextResolver
from llm_based.entity_linker import EntityLinker
from llm_based.graph_client import GraphClient
from llm_based.intent_planner import IntentPlanner
from llm_based.llm_client import LLMClient
from llm_based.question_rewriter import QuestionRewriter
from llm_based.runtime import api_response, setup_logging
from llm_based.session_store import SessionStore
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
        self.question_rewriter = QuestionRewriter(self.llm_client)
        self.context_resolver = ContextResolver()

    def chat(self, question, history=None, memory_context=None):
        fallback = "当前知识图谱中没有查到相关信息。"
        linked_entities = self.entity_linker.link(question)
        resolved_context = self.context_resolver.resolve(question, linked_entities, history or [])
        linked_entities = resolved_context.get("resolved_entities", linked_entities)
        if not linked_entities:
            return self._empty_response(question, fallback)

        planner_context = dict(memory_context or {})
        planner_context.update({
            "current_topic": resolved_context.get("current_topic"),
            "referenced_result": resolved_context.get("referenced_result"),
            "intent_hint": resolved_context.get("intent_hint"),
            "followup": resolved_context.get("followup"),
            "recent_result_entities": resolved_context.get("recent_result_entities"),
            "last_query_plan": resolved_context.get("last_query_plan"),
        })

        plan = self.intent_planner.plan(question, linked_entities, history=history, memory_context=planner_context)
        if not plan:
            return self._empty_response(question, fallback, linked_entities=linked_entities)

        subject = plan.get("subject", {})
        if not self.entity_linker.validate_entity(subject.get("name", ""), subject.get("label", "")):
            return self._empty_response(question, fallback, linked_entities=linked_entities, query_plan=plan)

        cypher, parameters = self.cypher_builder.build(plan)
        graph_results = self._graph_client().run(cypher, parameters)
        answer = self.answer_generator.generate(question, plan, graph_results, history=history)
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
                "memory_context": planner_context,
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
    elif plan.get("action") == "query_relation_chain":
        if subject_name:
            for item in results:
                first_node = item.get("node1")
                second_node = item.get("node2") or item.get("object")
                relation_name1 = item.get("relation_name1") or item.get("relation1") or "关系1"
                relation_name2 = item.get("relation_name2") or item.get("relation2") or "关系2"
                if first_node:
                    nodes[first_node] = {"id": first_node, "label": first_node, "type": "Entity"}
                    edges.append({"source": subject_name, "target": first_node, "label": relation_name1, "type": item.get("relation1", "")})
                if first_node and second_node:
                    nodes[second_node] = {"id": second_node, "label": second_node, "type": "Entity"}
                    edges.append({"source": first_node, "target": second_node, "label": relation_name2, "type": item.get("relation2", "")})
    return {"nodes": list(nodes.values()), "edges": edges}


def extract_result_entities(data):
    debug = data.get("debug", {})
    mode = data.get("mode")
    entities = []
    if mode == "llm_based":
        graph_results = debug.get("graph_results", [])
        plan = debug.get("query_plan", {})
        for item in graph_results:
            if item.get("object"):
                entities.append({"name": item["object"], "label": "Entity"})
            if plan.get("action") == "query_relation_chain":
                if item.get("node1"):
                    entities.append({"name": item["node1"], "label": "Entity"})
                if item.get("node2"):
                    entities.append({"name": item["node2"], "label": "Entity"})
    else:
        for item in debug.get("graph_results", []):
            if item.get("m.name"):
                entities.append({"name": item["m.name"], "label": "Entity"})
            if item.get("n.name"):
                entities.append({"name": item["n.name"], "label": "Entity"})

    deduped = []
    seen = set()
    for entity in entities:
        key = (entity.get("name"), entity.get("label"))
        if key[0] and key not in seen:
            deduped.append(entity)
            seen.add(key)
    return deduped[:10]


class AppHandler(SimpleHTTPRequestHandler):
    rule_service = None
    llm_service = None
    session_store = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        request_id = str(uuid.uuid4())
        if path == "/api/status":
            self.write_json(api_response(
                True,
                data={
                    "service": "Medical KG QA Studio",
                    "llm_configured": bool(self.llm_service.llm_client.api_key),
                    "active_sessions": self.session_store.session_count(),
                },
                request_id=request_id,
            ))
            return
        if path == "/api/session/status":
            self.write_json(api_response(
                True,
                data={"active_sessions": self.session_store.session_count()},
                request_id=request_id,
            ))
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        request_id = str(uuid.uuid4())
        started_at = time.time()
        try:
            payload = self.read_json()

            # 会话清除接口
            if path == "/api/session/clear":
                sid = (payload.get("session_id") or "").strip()
                if sid:
                    self.session_store.clear_session(sid)
                self.write_json(api_response(
                    True,
                    data={"cleared": bool(sid)},
                    request_id=request_id,
                    meta={"duration_ms": round((time.time() - started_at) * 1000, 2)},
                ))
                return

            question = (payload.get("question") or "").strip()
            if not question:
                self.write_json(
                    api_response(
                        False,
                        error={"message": "question is required"},
                        code="BAD_REQUEST",
                        request_id=request_id,
                        meta={"duration_ms": round((time.time() - started_at) * 1000, 2)},
                    ),
                    status=400,
                )
                return

            # 会话管理：获取或创建 session
            session_id = (payload.get("session_id") or "").strip()
            session = None
            if session_id:
                session = self.session_store.get_session(session_id)
            if not session:
                session_id = self.session_store.create_session()
                session = self.session_store.get_session(session_id)

            history = session.get("history", []) if session else []
            memory_context = session.get("memory_context", {}) if session else {}

            if path == "/api/rule/chat":
                data = self.rule_service.chat(question)
            elif path == "/api/llm/chat":
                # 问题改写：将代词/省略还原为完整问题
                effective_question = self.llm_service.question_rewriter.rewrite(question, history)
                data = self.llm_service.chat(effective_question, history=history, memory_context=memory_context)
                if effective_question != question:
                    data["original_question"] = question
                    data["rewritten_question"] = effective_question
            else:
                self.write_json(
                    api_response(
                        False,
                        error={"message": "not found"},
                        code="NOT_FOUND",
                        request_id=request_id,
                        meta={"duration_ms": round((time.time() - started_at) * 1000, 2)},
                    ),
                    status=404,
                )
                return

            # 记录本轮对话到 session
            self.session_store.add_turn(session_id, "user", question=question)
            self.session_store.add_turn(
                session_id, "assistant",
                answer=data.get("answer", ""),
                entities=data.get("debug", {}).get("linked_entities", []),
                plan=data.get("debug", {}).get("query_plan", {}),
                result_entities=extract_result_entities(data),
                graph_results=data.get("debug", {}).get("graph_results", [])[:8],
            )
            data["session_id"] = session_id
            logging.getLogger("web_app").info(
                "request ok path=%s request_id=%s duration_ms=%.2f",
                path, request_id, (time.time() - started_at) * 1000,
            )
            self.write_json(api_response(
                True,
                data=data,
                request_id=request_id,
                meta={"duration_ms": round((time.time() - started_at) * 1000, 2)},
            ))
        except Exception as exc:
            logging.getLogger("web_app").exception("request failed: path=%s", path)
            self.write_json(
                api_response(
                    False,
                    error={"message": str(exc)},
                    code="INTERNAL_ERROR",
                    request_id=request_id,
                    meta={"duration_ms": round((time.time() - started_at) * 1000, 2)},
                ),
                status=500,
            )

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
    setup_logging()
    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8000"))
    AppHandler.rule_service = RuleQAService()
    AppHandler.llm_service = LLMQAService()
    AppHandler.session_store = SessionStore(llm_client=AppHandler.llm_service.llm_client)
    server = ThreadingHTTPServer((host, port), AppHandler)
    logging.getLogger("web_app").info("Medical KG QA Studio: http://%s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()

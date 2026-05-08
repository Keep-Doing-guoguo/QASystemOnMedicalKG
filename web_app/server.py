#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/8 18:42
@source from: 
"""
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

from llm_base.answer_generator import AnswerGenerator
from llm_base.cypher_builder import CypherBuilder
from llm_base.content_resolver import ContextResolver
from llm_base.entity_link import EntityLinker
from llm_base.graph_client import GraphClient
from llm_base.intent_planner import IntentPlanner
from llm_base.llm_client import LLMClient
from llm_base.question_rewriter import QuestionRewriter
from llm_base.runtime import api_response, setup_logging
from llm_base.session_store import SessionStore

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

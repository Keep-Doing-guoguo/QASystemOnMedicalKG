#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/7 19:39
@source from: 
"""
ENTITY_LABELS = {
    "disease": "Disease",
    "symptom": "Symptom",
    "drug": "Drug",
    "food": "Food",
    "check": "Check",
    "department": "Department",
    "producer": "Producer",
}

PROPERTY_QUERIES = {
    "desc": {"label": "Disease", "property": "desc", "name": "疾病简介"},
    "cause": {"label": "Disease", "property": "cause", "name": "疾病病因"},
    "prevent": {"label": "Disease", "property": "prevent", "name": "预防措施"},
    "cure_lasttime": {"label": "Disease", "property": "cure_lasttime", "name": "治疗周期"},
    "cure_way": {"label": "Disease", "property": "cure_way", "name": "治疗方式"},
    "cured_prob": {"label": "Disease", "property": "cured_prob", "name": "治愈概率"},
    "easy_get": {"label": "Disease", "property": "easy_get", "name": "易感人群"},
}

RELATION_QUERIES = {
    "has_symptom": {
        "start_label": "Disease",
        "end_label": "Symptom",
        "name": "疾病症状",
    },
    "acompany_with": {
        "start_label": "Disease",
        "end_label": "Disease",
        "name": "并发疾病",
    },
    "no_eat": {
        "start_label": "Disease",
        "end_label": "Food",
        "name": "忌食",
    },
    "do_eat": {
        "start_label": "Disease",
        "end_label": "Food",
        "name": "宜食",
    },
    "recommand_eat": {
        "start_label": "Disease",
        "end_label": "Food",
        "name": "推荐食谱",
    },
    "common_drug": {
        "start_label": "Disease",
        "end_label": "Drug",
        "name": "常用药品",
    },
    "recommand_drug": {
        "start_label": "Disease",
        "end_label": "Drug",
        "name": "推荐药品",
    },
    "need_check": {
        "start_label": "Disease",
        "end_label": "Check",
        "name": "所需检查",
    },
    "drugs_of": {
        "start_label": "Producer",
        "end_label": "Drug",
        "name": "在售药品",
    },
    "belongs_to": {
        "start_label": "Department",
        "end_label": "Department",
        "name": "属于",
    },
}


SUPPORTED_ACTIONS = {"query_property", "query_relation", "query_relation_chain"}

CHAIN_TEMPLATES = {
    "symptom_to_drug": {
        "subject_label": "Symptom",
        "name": "症状->疾病->常用药品",
        "steps": [
            {"relation": "has_symptom", "direction": "incoming"},
            {"relation": "common_drug", "direction": "outgoing"},
        ],
    },
    "symptom_to_check": {
        "subject_label": "Symptom",
        "name": "症状->疾病->所需检查",
        "steps": [
            {"relation": "has_symptom", "direction": "incoming"},
            {"relation": "need_check", "direction": "outgoing"},
        ],
    },
    "food_to_drug": {
        "subject_label": "Food",
        "name": "食物->疾病->常用药品",
        "steps": [
            {"relation": "do_eat", "direction": "incoming"},
            {"relation": "common_drug", "direction": "outgoing"},
        ],
    },
    "drug_to_symptom": {
        "subject_label": "Drug",
        "name": "药品->疾病->症状",
        "steps": [
            {"relation": "common_drug", "direction": "incoming"},
            {"relation": "has_symptom", "direction": "outgoing"},
        ],
    },
}

def schema_for_prompt():
    """提供给 LLM 的 schema 摘要，让 LLM 只能在白名单内规划查询。"""
    return {
        "entity_labels": ENTITY_LABELS,
        "property_queries": PROPERTY_QUERIES,
        "relation_queries": RELATION_QUERIES,
        "chain_templates": CHAIN_TEMPLATES,
        "supported_actions": sorted(SUPPORTED_ACTIONS),
    }




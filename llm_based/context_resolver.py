#!/usr/bin/env python3
# coding: utf-8

from llm_based.schema import ENTITY_LABELS


FOLLOWUP_CUES = ["那", "它", "他", "她", "这个", "那个", "该病", "这种病", "这种药", "呢", "再", "继续"]
ORDINAL_MAP = {
    "第一个": 0,
    "第1个": 0,
    "第二个": 1,
    "第2个": 1,
    "第三个": 2,
    "第3个": 2,
    "最后一个": -1,
}
INTENT_HINTS = [
    ("症状", "has_symptom", "outgoing"),
    ("病因", "cause", None),
    ("原因", "cause", None),
    ("预防", "prevent", None),
    ("多久", "cure_lasttime", None),
    ("治疗", "cure_way", None),
    ("治好", "cured_prob", None),
    ("易感", "easy_get", None),
    ("吃什么药", "common_drug", "outgoing"),
    ("什么药", "common_drug", "outgoing"),
    ("不能吃", "no_eat", "outgoing"),
    ("适合吃", "do_eat", "outgoing"),
    ("吃什么", "do_eat", "outgoing"),
    ("做什么检查", "need_check", "outgoing"),
    ("查什么病", "symptom_to_check", "chain"),
    ("吃什么药", "symptom_to_drug", "chain"),
    ("用什么药", "symptom_to_drug", "chain"),
]


class ContextResolver:
    def resolve(self, question, linked_entities, history):
        state = self._extract_state(history)
        resolved_entities = list(linked_entities or [])
        topic = state.get("current_topic")
        followup = self._looks_like_followup(question, resolved_entities)

        if not resolved_entities and topic and followup:
            resolved_entities.append({
                "name": topic["name"],
                "types": [self._type_for_label(topic["label"])],
                "labels": [topic["label"]],
            })

        referenced = self._resolve_referenced_result(question, state)
        if referenced:
            if not any(item.get("name") == referenced["name"] for item in resolved_entities):
                resolved_entities.append({
                    "name": referenced["name"],
                    "types": [self._type_for_label(referenced["label"])],
                    "labels": [referenced["label"]],
                })

        return {
            "resolved_entities": resolved_entities,
            "current_topic": topic,
            "referenced_result": referenced,
            "followup": followup,
            "intent_hint": self._infer_intent_hint(question),
            "last_query_plan": state.get("last_query_plan", {}),
            "recent_result_entities": state.get("recent_result_entities", []),
        }

    def _extract_state(self, history):
        current_topic = None
        last_query_plan = {}
        recent_result_entities = []
        for turn in reversed(history or []):
            if turn.get("role") != "assistant":
                continue
            plan = turn.get("plan") or {}
            if not last_query_plan and plan:
                last_query_plan = plan
            subject = plan.get("subject")
            if not current_topic and isinstance(subject, dict) and subject.get("name") and subject.get("label"):
                current_topic = {"name": subject["name"], "label": subject["label"]}
            if not recent_result_entities:
                recent_result_entities = turn.get("result_entities", []) or []
            if current_topic and last_query_plan and recent_result_entities:
                break
        return {
            "current_topic": current_topic,
            "last_query_plan": last_query_plan,
            "recent_result_entities": recent_result_entities,
        }

    @staticmethod
    def _looks_like_followup(question, linked_entities):
        if linked_entities:
            return any(cue in question for cue in FOLLOWUP_CUES)
        return any(cue in question for cue in FOLLOWUP_CUES) or len(question.strip()) <= 10

    @staticmethod
    def _resolve_referenced_result(question, state):
        results = state.get("recent_result_entities", [])
        if not results:
            return None
        for key, index in ORDINAL_MAP.items():
            if key in question:
                try:
                    return results[index]
                except IndexError:
                    return None
        return None

    @staticmethod
    def _infer_intent_hint(question):
        for keyword, target, direction in INTENT_HINTS:
            if keyword in question:
                if direction == "chain":
                    return {"type": "chain", "target": target}
                if direction is None:
                    return {"type": "property", "target": target}
                return {"type": "relation", "target": target, "direction": direction}
        return {}

    @staticmethod
    def _type_for_label(label):
        for entity_type, entity_label in ENTITY_LABELS.items():
            if entity_label == label:
                return entity_type
        return ""

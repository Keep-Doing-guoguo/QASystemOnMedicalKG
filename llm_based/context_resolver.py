#!/usr/bin/env python3
# coding: utf-8

from llm_based.schema import ENTITY_LABELS


# 这些词通常表示用户当前问题依赖上一轮上下文，需要结合历史解析。
FOLLOWUP_CUES = ["那", "它", "他", "她", "这个", "那个", "该病", "这种病", "这种药", "呢", "再", "继续"]

# 将“第一个/第二个/最后一个”等自然语言引用映射到上一轮结果实体下标。
ORDINAL_MAP = {
    "第一个": 0,
    "第1个": 0,
    "第二个": 1,
    "第2个": 1,
    "第三个": 2,
    "第3个": 2,
    "最后一个": -1,
}

# 从当前问题中快速提取意图提示，帮助 IntentPlanner 在追问场景下生成稳定计划。
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
    """多轮对话上下文解析器。

    负责在进入 LLM 查询规划之前，从历史对话中恢复当前主题、上一轮查询计划、
    最近结果实体，并识别用户是否在追问或引用上一轮结果。

    典型用途：
    - 用户问“那它适合吃什么？”时，恢复“它”对应的上一轮疾病实体。
    - 用户问“第二个还能治什么？”时，解析“第二个”对应的上一轮结果实体。
    - 从“不能吃/适合吃/病因”等关键词中推断当前问题的大致意图。
    """

    def resolve(self, question, linked_entities, history):
        """解析当前问题需要的上下文信息。

        Args:
            question: 当前用户问题。
            linked_entities: 当前问题直接识别出的实体列表。
            history: 当前 session 的历史对话 turn 列表。

        Returns:
            dict: 上下文解析结果，包括：
                resolved_entities: 合并当前识别实体与历史补全实体后的实体列表。
                current_topic: 最近一次对话主题实体。
                referenced_result: “第一个/第二个”等指代到的历史结果实体。
                followup: 当前问题是否像追问。
                intent_hint: 从当前问题关键词推断出的意图提示。
                last_query_plan: 最近一次 assistant 保存的查询计划。
                recent_result_entities: 最近一次图谱结果实体列表。
        """
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
        """从历史对话中提取最近的会话状态。

        只关注 assistant turn，因为 assistant turn 中保存了结构化 plan、
        result_entities 等程序可读信息。

        Args:
            history: 当前 session 的历史 turn 列表。

        Returns:
            dict: 包含 current_topic、last_query_plan、recent_result_entities。
        """
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
        """判断当前问题是否像追问。

        如果问题已经识别出实体，则只有包含追问提示词时才认为是追问；
        如果没有识别出实体，短问题或包含指代词的问题更可能依赖上下文。

        Args:
            question: 当前用户问题。
            linked_entities: 当前问题直接识别出的实体列表。

        Returns:
            bool: 是否像追问。
        """
        if linked_entities:
            return any(cue in question for cue in FOLLOWUP_CUES)
        return any(cue in question for cue in FOLLOWUP_CUES) or len(question.strip()) <= 10

    @staticmethod
    def _resolve_referenced_result(question, state):
        """解析用户对上一轮结果实体的序号引用。

        例如用户问“第二个还能治什么病？”，则从 recent_result_entities
        中取下标 1 的实体返回。

        Args:
            question: 当前用户问题。
            state: _extract_state 返回的历史状态。

        Returns:
            dict | None: 被引用的结果实体；如果无法解析则返回 None。
        """
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
        """根据关键词推断当前问题的意图提示。

        该函数不直接生成最终查询计划，只给 IntentPlanner 提供辅助信息，
        例如“不能吃” -> no_eat，“病因” -> cause。

        Args:
            question: 当前用户问题。

        Returns:
            dict: 意图提示，可能是 property/relation/chain；无法判断时返回空 dict。
        """
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
        """将图谱 Label 反查为实体类型名称。

        Args:
            label: 图谱节点标签，例如 Disease、Drug、Food。

        Returns:
            str: 项目内部实体类型，例如 disease、drug、food；无法匹配时返回空字符串。
        """
        for entity_type, entity_label in ENTITY_LABELS.items():
            if entity_label == label:
                return entity_type
        return ""

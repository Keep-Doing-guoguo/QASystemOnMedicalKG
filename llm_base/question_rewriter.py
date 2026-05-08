#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/7 21:33
@source from: 
"""
# 需要触发改写检测的代词 / 指示词
_INDICATORS = ["它", "他", "她", "这个", "那个", "那", "此", "上述", "同上"]
class QuestionRewriter:
    """在实体识别之前，利用对话历史将不完整问题改写为独立问题。

    例如用户先问"板蓝根颗粒能治什么病"，再问"它的副作用呢"，
    改写器会输出"板蓝根颗粒的副作用"，使后续实体识别正常工作。
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def rewrite(self, question, history):
        """

        返回改写后的问题字符串。无历史或无需改写时原样返回。

        1. 如果没有历史，直接返回原问题
        2. 如果问题里没有“它、那、这个”等指代词，直接返回原问题
        3. 先用规则方法 heuristic 改写
        4. 如果规则改写成功，直接返回
        5. 如果规则改写不出来，再调用 LLM 改写
        6. 如果 LLM 也失败，返回原问题

        """
        if not history:
            return question

        if not self._needs_rewrite(question):
            return question

        heuristic = self._heuristic_rewrite(question, history)
        if heuristic != question:
            return heuristic

        try:
            rewritten = self.llm_client.chat_text(
                self._system_prompt(),
                {
                    "conversation_history": self._format_history(history),
                    "current_question": question,
                },
            )
            if rewritten and isinstance(rewritten, str):
                rewritten = rewritten.strip()
                if rewritten:
                    return rewritten
        except Exception:
            pass
        return question
    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    #判断当前问题是否需要改写。
    @staticmethod
    def _needs_rewrite(question):
        return any(ind in question for ind in _INDICATORS)

    #规则改写逻辑。
    def _heuristic_rewrite(self, question, history):
        topic = self._latest_topic(history)
        if not topic:
            return question

        rewritten = question
        for pronoun in ["它", "他", "她", "这个", "那个", "该病", "这种病", "这种药"]:
            if pronoun in rewritten:
                rewritten = rewritten.replace(pronoun, topic)
        if rewritten != question:
            return rewritten

        stripped = question.strip()
        if stripped.startswith("那") and stripped.endswith("呢"):
            return topic + stripped[1:]#那病因呢 -》 高血压病因呢
        return question
    @staticmethod#从历史对话里找最近的实体主题。倒序看最近 8 条历史
    def _latest_topic(history):
        for turn in reversed(history[-8:]):
            plan = turn.get("plan") or {}
            subject = plan.get("subject") or {}
            if subject.get("name"):
                return subject["name"]
            entities = turn.get("entities") or []
            if entities:
                first = entities[0]
                if isinstance(first, dict) and first.get("name"):
                    return first["name"]
            return ""

    #把历史对话格式化成文本，给 LLM 看。
    @staticmethod
    def _format_history(history):
        """取最近 3 轮 QA（6 条 turn）转为可读文本。"""
        lines = []
        for turn in history[-6:]:
            role = turn.get("role")
            if role == "user":
                lines.append("用户：" + turn.get("question", ""))
            elif role == "assistant":
                lines.append("助手：" + turn.get("answer", "")[:200])
        return "\n".join(lines)

    @staticmethod
    def _system_prompt():
        return (
            "你是医疗问答系统的问题改写器。\n"
            "根据对话历史，将用户当前的问题改写为一个独立、完整的医疗问题。\n"
            "规则：\n"
            "1. 将代词（它、他、她）替换为对话历史中最近提到的具体实体。\n"
            "2. 将省略的内容（如\"那高血压呢\"）补全为完整问题（如\"高血压吃什么药\"）。\n"
            "3. 如果问题已经是完整的，直接返回原问题。\n"
            "4. 只输出改写后的问题，不要解释。\n"
            "5. 如果无法判断，返回原问题。"
        )
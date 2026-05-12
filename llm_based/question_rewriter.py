#!/usr/bin/env python3
# coding: utf-8


# 需要触发改写检测的代词 / 指示词。
# 当前问题包含这些词时，说明它可能依赖上一轮上下文。
_INDICATORS = ["它", "他", "她", "这个", "那个", "那", "此", "上述", "同上"]


class QuestionRewriter:
    """在实体识别之前，利用对话历史将不完整问题改写为独立问题。

    例如用户先问"板蓝根颗粒能治什么病"，再问"它的副作用呢"，
    改写器会输出"板蓝根颗粒的副作用"，使后续实体识别正常工作。
    """

    def __init__(self, llm_client):
        """初始化问题改写器。

        Args:
            llm_client: LLM 客户端。规则改写无法处理时，用它调用大模型兜底改写。
        """
        self.llm_client = llm_client

    def rewrite(self, question, history):
        """返回改写后的问题字符串。

        改写流程：
        1. 没有历史时，直接返回原问题。
        2. 当前问题不包含指代词/追问词时，直接返回原问题。
        3. 优先使用规则方法从历史中找最近主题并替换代词。
        4. 规则无法改写时，再调用 LLM 根据历史兜底改写。
        5. LLM 失败或返回空内容时，返回原问题。

        Args:
            question: 当前用户问题。
            history: 当前 session 的历史对话 turn 列表。

        Returns:
            str: 改写后的完整问题；无法改写时返回原问题。
        """
        if not history:
            return question

        if not self._needs_rewrite(question):
            return question

        heuristic = self._heuristic_rewrite(question, history)
        if heuristic != question:
            return heuristic

        # 规则无法找到明确主题时，再让 LLM 基于最近历史进行语义改写。
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

    @staticmethod
    def _needs_rewrite(question):
        """判断当前问题是否包含需要改写的指代词或追问提示词。

        Args:
            question: 当前用户问题。

        Returns:
            bool: 如果包含 _INDICATORS 中任意词，则返回 True。
        """
        return any(ind in question for ind in _INDICATORS)

    def _heuristic_rewrite(self, question, history):
        """使用规则进行快速改写。

        规则改写不调用 LLM，主要做两件事：
        - 从历史中找最近主题实体，例如“高血压”。
        - 将“它/这个/该病”等代词替换成该主题。

        Args:
            question: 当前用户问题。
            history: 当前 session 的历史对话 turn 列表。

        Returns:
            str: 改写后的问题；如果规则无法处理则返回原问题。
        """
        topic = self._latest_topic(history)
        if not topic:
            return question

        rewritten = question
        # 直接替换明确代词，例如“它怎么治疗？” -> “高血压怎么治疗？”。
        for pronoun in ["它", "他", "她", "这个", "那个", "该病", "这种病", "这种药"]:
            if pronoun in rewritten:
                rewritten = rewritten.replace(pronoun, topic)
        if rewritten != question:
            return rewritten

        stripped = question.strip()
        if stripped.startswith("那") and stripped.endswith("呢"):
            # 处理省略追问，例如“那病因呢” -> “高血压病因呢”。
            return topic + stripped[1:]
        return question

    @staticmethod
    def _latest_topic(history):
        """从历史对话中查找最近的主题实体。

        优先读取 assistant turn 中保存的 query plan：
        plan.subject.name 通常是上一轮图谱查询的中心实体。
        如果没有 plan，则退回到 assistant turn 中保存的 entities。

        Args:
            history: 当前 session 的历史对话 turn 列表。

        Returns:
            str: 最近主题实体名称；如果找不到则返回空字符串。
        """
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

    @staticmethod
    def _format_history(history):
        """将最近历史对话格式化为 LLM 可读文本。

        只取最近 6 条 turn，约等于最近 3 轮 QA，避免提示词过长。

        Args:
            history: 当前 session 的历史对话 turn 列表。

        Returns:
            str: 形如“用户：...\n助手：...”的历史文本。
        """
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
        """返回用于 LLM 兜底改写的系统提示词。

        Returns:
            str: 约束 LLM 只输出改写后问题的提示词。
        """
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

#!/usr/bin/env python3
# coding: utf-8


class MemoryCompressor:
    """使用 LLM 将旧对话轮次压缩为摘要文本。

    压缩后的内容用于注入 intent_planner / answer_generator 的 prompt，
    让 LLM 在不消耗大量 token 的情况下了解早期对话背景。
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def compress(self, old_turns, existing_summary=""):
        """将旧轮次压缩为一段摘要文本。

        Args:
            old_turns: list of dicts, 每个含 role/question/answer
            existing_summary: 已有的旧摘要，需要与新内容合并

        Returns:
            str: 压缩后的摘要文本
        """
        if not old_turns and not existing_summary:
            return ""

        turns_text = self._format_turns(old_turns)

        try:
            result = self.llm_client.chat_text(
                self._system_prompt(),
                {
                    "existing_summary": existing_summary,
                    "turns": turns_text,
                },
            )
            if result and isinstance(result, str) and result.strip():
                return result.strip()
        except Exception:
            pass

        # LLM 失败时降级为简单拼接
        return self._fallback_compress(old_turns, existing_summary)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _format_turns(turns):
        lines = []
        for turn in turns:
            role = turn.get("role", "")
            if role == "user":
                lines.append("用户：" + turn.get("question", ""))
            elif role == "assistant":
                answer = turn.get("answer", "")
                lines.append("助手：" + answer[:150])
        return "\n".join(lines)

    @staticmethod
    def _fallback_compress(turns, existing_summary):
        """LLM 不可用时的降级压缩。"""
        topics = []
        for turn in turns:
            if turn.get("role") == "user" and turn.get("question"):
                topics.append(turn["question"])
        new_part = "；".join(topics[-5:])
        if existing_summary:
            return existing_summary + "；" + new_part
        return new_part

    @staticmethod
    def _system_prompt():
        return (
            "你是对话摘要压缩器。将用户与助手的对话历史压缩为简洁摘要。\n"
            "规则：\n"
            "1. 提取用户咨询的核心主题（疾病名称、药品名称、查询类型）\n"
            "2. 如果有 existing_summary，将其与新对话合并，去除重复\n"
            "3. 摘要不超过 200 字\n"
            "4. 使用中文，格式如：用户此前咨询了：1. 感冒的症状与用药；2. 高血压的病因\n"
            "5. 只输出摘要文本，不要解释"
        )

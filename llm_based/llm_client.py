import json
import http.client
import socket
import urllib.error
import urllib.request

try:
    from llm_based.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, LLM_MAX_RETRIES
except ModuleNotFoundError:
    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, LLM_MAX_RETRIES


class LLMClient:
    """OpenAI-compatible Chat Completions 客户端。

    当前用于 DashScope 兼容模式，也可以替换为其他兼容服务。
    """

    def __init__(self, api_key=None, base_url=None, model=None):
        self.debug = True
        self.api_key = api_key if api_key is not None else LLM_API_KEY
        self.base_url = (base_url if base_url is not None else LLM_BASE_URL).rstrip("/")
        self.model = model if model is not None else LLM_MODEL
        # 记录最近一次失败原因，供 chatbot_graph debug 输出。
        self.last_error = ""

    def chat_json(self, system_prompt, user_payload):
        """请求 LLM 返回 JSON 对象，用于查询计划生成。"""
        if not self.api_key:
            return {}

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        self.debug_print("chat_json_payload", self._safe_payload(payload))
        return self._post_chat(payload)

    def chat_text(self, system_prompt, user_payload):
        """请求 LLM 返回普通文本，用于自然语言答案生成。"""
        if not self.api_key:
            return ""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": 0.2,
        }
        self.debug_print("chat_text_payload", self._safe_payload(payload))
        body = self._post_chat(payload)
        return body.get("content", "") if isinstance(body, dict) else ""

    def _post_chat(self, payload):
        """发送 Chat Completions 请求并解析 choices[0].message.content。"""
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=data,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "medical-kg-qa/1.0",
            },
            method="POST",
        )
        body = self._send_with_retries(request)
        if not body:
            self.debug_print("response_body", body)
            return {}

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        self.debug_print("response_content", content)
        if payload.get("response_format", {}).get("type") == "json_object":
            try:
                # json_object 模式下，content 本身仍是字符串，需要二次解析。
                parsed = json.loads(content)
                self.debug_print("response_json", parsed)
                return parsed
            except json.JSONDecodeError:
                self.debug_print("json_decode_error", content)
                return {}
        return {"content": content}

    def _send_with_retries(self, request):
        """处理 HTTPS 偶发断连，并对可重试网络异常做有限重试。"""
        self.last_error = ""
        for attempt in range(LLM_MAX_RETRIES + 1):
            try:
                self.debug_print("request_attempt", attempt + 1)
                with urllib.request.urlopen(request, timeout=LLM_TIMEOUT) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    self.last_error = ""
                    self.debug_print("http_status", response.status)
                    return body
            except urllib.error.HTTPError as error:
                # HTTP 4xx/5xx 通常不是重试能解决的问题，直接记录并返回。
                detail = error.read().decode("utf-8", errors="replace")
                self.last_error = "HTTPError {0}: {1}".format(error.code, detail[:500])
                self.debug_print("last_error", self.last_error)
                return {}
            except (
                urllib.error.URLError,
                TimeoutError,
                socket.timeout,
                ConnectionError,
                http.client.HTTPException,
                json.JSONDecodeError,
            ) as error:
                # 网络抖动、TLS EOF、远端断连等错误允许重试。
                self.last_error = "{0}: {1}".format(type(error).__name__, error)
                self.debug_print("last_error", self.last_error)
                if attempt >= LLM_MAX_RETRIES:
                    return {}
        return {}

    def _safe_payload(self, payload):
        """返回适合日志输出的 payload，避免内容太长。"""
        safe = dict(payload)
        safe["url"] = self.base_url + "/chat/completions"
        safe["messages"] = [
            {
                "role": message.get("role"),
                "content": self._shorten(message.get("content", "")),
            }
            for message in payload.get("messages", [])
        ]
        return safe

    def _shorten(self, text, limit=800):
        text = str(text)
        if len(text) <= limit:
            return text
        return text[:limit] + "...<truncated>"

    def debug_print(self, name, value):
        if self.debug:
            print("[LLMClient] {0}: {1}".format(name, value))

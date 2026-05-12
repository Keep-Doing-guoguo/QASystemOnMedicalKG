#!/usr/bin/env python3
# coding: utf-8

import logging
import os
import time
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from llm_based.runtime import api_response, setup_logging
from llm_based.session_store import SessionStore
from web_app.server import LLMQAService, RuleQAService, STATIC_DIR, extract_result_entities


class ChatRequest(BaseModel):
    """聊天接口请求体。

    question 是用户当前问题；session_id 用于多轮会话和长期记忆。
    如果 session_id 为空，服务端会自动创建一个新会话。
    """

    question: str = Field(
        "",
        description="用户输入的医疗问题。",
        examples=["高血压不能吃什么？"],
    )
    session_id: str = Field(
        "",
        description="可选。用于连续对话和记忆测试；同一个 session_id 会复用历史上下文。",
        examples=["debug-memory-002"],
    )


class ClearSessionRequest(BaseModel):
    """清空会话接口请求体。"""

    session_id: str = Field(
        "",
        description="要清空的会话 ID。",
        examples=["debug-memory-002"],
    )


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。

    这里完成：
    - 初始化日志
    - 创建规则问答服务、LLM 问答服务和会话存储
    - 注册 API 路由
    - 注册异常处理器
    - 挂载前端静态资源目录

    Returns:
        FastAPI: 已完成路由和状态初始化的应用实例。
    """
    setup_logging()
    app = FastAPI(title="Medical KG QA Studio", version="1.0.0")

    # 服务实例挂到 app.state 上，避免每个请求重复初始化词典、LLM 客户端和会话库。
    app.state.rule_service = RuleQAService()
    app.state.llm_service = LLMQAService()
    app.state.session_store = SessionStore(llm_client=app.state.llm_service.llm_client)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """统一处理 HTTP 异常。

        API 路径返回项目统一响应结构；非 API 路径保留 FastAPI/Starlette
        的普通 JSON 错误结构，避免影响静态资源访问。
        """
        if request.url.path.startswith("/api/"):
            request_id = str(uuid.uuid4())
            return JSONResponse(
                api_response(
                    False,
                    error={"message": "not found" if exc.status_code == 404 else str(exc.detail)},
                    code="NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
                    request_id=request_id,
                ),
                status_code=exc.status_code,
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        """统一处理未捕获异常，返回 INTERNAL_ERROR。"""
        request_id = str(uuid.uuid4())
        logging.getLogger("web_app.fastapi").exception("request failed: path=%s", request.url.path)
        return JSONResponse(
            api_response(
                False,
                error={"message": str(exc)},
                code="INTERNAL_ERROR",
                request_id=request_id,
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.get("/api/status")
    def api_status() -> Dict[str, Any]:
        """返回服务状态。

        包括服务名称、LLM API Key 是否配置、当前活跃 session 数。
        """
        request_id = str(uuid.uuid4())
        return api_response(
            True,
            data={
                "service": "Medical KG QA Studio",
                "llm_configured": bool(app.state.llm_service.llm_client.api_key),
                "active_sessions": app.state.session_store.session_count(),
            },
            request_id=request_id,
        )

    @app.get("/api/session/status")
    def session_status() -> Dict[str, Any]:
        """返回当前持久化 session 数量。"""
        request_id = str(uuid.uuid4())
        return api_response(
            True,
            data={"active_sessions": app.state.session_store.session_count()},
            request_id=request_id,
        )

    @app.post("/api/session/clear")
    async def clear_session(payload: ClearSessionRequest) -> Dict[str, Any]:
        """清空指定 session 的历史对话和摘要记忆。"""
        request_id = str(uuid.uuid4())
        started_at = time.time()
        sid = payload.session_id.strip()
        if sid:
            app.state.session_store.clear_session(sid)
        return api_response(
            True,
            data={"cleared": bool(sid)},
            request_id=request_id,
            meta=duration_meta(started_at),
        )

    @app.post("/api/rule/chat")
    async def rule_chat(payload: ChatRequest):
        """规则版问答接口。

        复用 handle_chat 中的请求校验、session 创建和 turn 记录逻辑；
        实际回答由 RuleQAService 完成。
        """
        return handle_chat(app, "/api/rule/chat", payload_to_dict(payload))

    @app.post("/api/llm/chat")
    async def llm_chat(payload: ChatRequest):
        """LLM 增强版问答接口。

        支持 session 历史、追问改写、memory_context 和图谱查询计划生成。
        """
        return handle_chat(app, "/api/llm/chat", payload_to_dict(payload))

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def handle_chat(app: FastAPI, path: str, payload: Dict[str, Any]):
    """处理规则版和 LLM 版聊天接口的公共流程。

    Args:
        app: FastAPI 应用实例，用于读取 app.state 中的服务对象。
        path: 当前接口路径，用于区分规则问答和 LLM 问答。
        payload: 请求体字典，包含 question 和可选 session_id。

    Returns:
        dict | JSONResponse: 成功时返回统一响应 dict；校验失败或异常时返回
        带 HTTP 状态码的 JSONResponse。
    """
    request_id = str(uuid.uuid4())
    started_at = time.time()
    try:
        question = (payload.get("question") or "").strip()
        if not question:
            return JSONResponse(
                api_response(
                    False,
                    error={"message": "question is required"},
                    code="BAD_REQUEST",
                    request_id=request_id,
                    meta=duration_meta(started_at),
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        session_id = (payload.get("session_id") or "").strip()
        # 优先复用客户端传入的 session_id；不存在时按该 id 创建，便于跨窗口继续会话。
        session = app.state.session_store.get_session(session_id) if session_id else None
        if not session:
            session_id = app.state.session_store.create_session(session_id)
            session = app.state.session_store.get_session(session_id)

        history = session.get("history", []) if session else []
        memory_context = session.get("memory_context", {}) if session else {}

        if path == "/api/rule/chat":
            data = app.state.rule_service.chat(question)
        else:
            # LLM 链路先基于历史改写追问，再带 history/memory_context 进行查询规划。
            effective_question = app.state.llm_service.question_rewriter.rewrite(question, history)
            data = app.state.llm_service.chat(
                effective_question,
                history=history,
                memory_context=memory_context,
            )
            if effective_question != question:
                data["original_question"] = question
                data["rewritten_question"] = effective_question

        # 记录本轮 user/assistant turn，供后续长会话和指代消解使用。
        app.state.session_store.add_turn(session_id, "user", question=question)
        app.state.session_store.add_turn(
            session_id,
            "assistant",
            answer=data.get("answer", ""),
            entities=data.get("debug", {}).get("linked_entities", []),
            plan=data.get("debug", {}).get("query_plan", {}),
            result_entities=extract_result_entities(data),
            graph_results=data.get("debug", {}).get("graph_results", [])[:8],
        )
        data["session_id"] = session_id
        logging.getLogger("web_app.fastapi").info(
            "request ok path=%s request_id=%s duration_ms=%.2f",
            path,
            request_id,
            (time.time() - started_at) * 1000,
        )
        return api_response(
            True,
            data=data,
            request_id=request_id,
            meta=duration_meta(started_at),
        )
    except Exception as exc:
        logging.getLogger("web_app.fastapi").exception("request failed: path=%s", path)
        return JSONResponse(
            api_response(
                False,
                error={"message": str(exc)},
                code="INTERNAL_ERROR",
                request_id=request_id,
                meta=duration_meta(started_at),
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def payload_to_dict(payload: BaseModel) -> Dict[str, Any]:
    """兼容 Pydantic v1/v2，将请求模型转换为 dict。"""
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def duration_meta(started_at: float) -> Dict[str, float]:
    """根据开始时间生成接口耗时元信息。"""
    return {"duration_ms": round((time.time() - started_at) * 1000, 2)}


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

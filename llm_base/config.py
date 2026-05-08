#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/7 21:50
@source from: 
"""
from llm_base.runtime import env_bool, env_int, env_str


# OpenAI-compatible Chat Completions 配置。
LLM_API_KEY = env_str("LLM_API_KEY", "")
LLM_BASE_URL = env_str("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = env_str("LLM_MODEL", "qwen-turbo")
LLM_TIMEOUT = env_int("LLM_TIMEOUT", 60)
LLM_MAX_RETRIES = env_int("LLM_MAX_RETRIES", 2)
LLM_DEBUG = env_bool("LLM_DEBUG", False)
APP_DEBUG = env_bool("APP_DEBUG", False)

# Neo4j
NEO4J_URI = env_str("NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = env_str("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = env_str("NEO4J_PASSWORD", "12341234")
NEO4J_DEBUG = env_bool("NEO4J_DEBUG", False)

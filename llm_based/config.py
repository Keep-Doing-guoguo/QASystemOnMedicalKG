# OpenAI-compatible Chat Completions 配置。
# 当前示例使用阿里云 DashScope 兼容模式；如更换服务商，只需要改这里。
LLM_API_KEY = "sk-3207e60e41894d76bdc149bbb3cf867f"
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen-turbo"
LLM_TIMEOUT = 30
# HTTPS 偶发 EOF / 远端断连时自动重试次数。
LLM_MAX_RETRIES = 2

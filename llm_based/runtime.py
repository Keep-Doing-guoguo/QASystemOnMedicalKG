import logging
import os


def env_str(name, default=""):
    """读取字符串环境变量。

    Args:
        name: 环境变量名称。
        default: 环境变量不存在时返回的默认值。

    Returns:
        str: 环境变量值；如果未设置则返回 default。
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value


def env_int(name, default):
    """读取整数环境变量。

    Args:
        name: 环境变量名称。
        default: 环境变量不存在、为空或无法转换为整数时的默认值。

    Returns:
        int: 转换后的整数值，或 default。
    """
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name, default=False):
    """读取布尔环境变量。

    识别 1/true/yes/on 为 True，大小写不敏感；其他值为 False。

    Args:
        name: 环境变量名称。
        default: 环境变量不存在时返回的默认值。

    Returns:
        bool: 解析后的布尔值。
    """
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def setup_logging():
    """初始化全局日志配置。

    日志级别从 APP_LOG_LEVEL 环境变量读取，默认 INFO。
    输出格式包含时间、级别、logger 名称和日志内容。
    """
    level_name = env_str("APP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_logger(name):
    """获取指定名称的 logger。

    Args:
        name: logger 名称，通常使用模块或业务组件名。

    Returns:
        logging.Logger: Python 标准库 logger 实例。
    """
    return logging.getLogger(name)


def api_response(ok, data=None, error=None, code="OK", request_id="", meta=None):
    """构造统一 API 响应结构。

    Args:
        ok: 请求是否成功。
        data: 成功时返回的数据对象；None 会被转换为空 dict。
        error: 失败时返回的错误信息对象。
        code: 业务状态码，默认 OK。
        request_id: 请求唯一标识，便于日志追踪。
        meta: 元信息，例如耗时 duration_ms。

    Returns:
        dict: 统一响应字典，包含 ok/code/request_id/data/error/meta。
    """
    return {
        "ok": ok,
        "code": code,
        "request_id": request_id,
        "data": data if data is not None else {},
        "error": error,
        "meta": meta or {},
    }

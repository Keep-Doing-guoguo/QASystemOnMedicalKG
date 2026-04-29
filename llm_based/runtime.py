import logging
import os


def env_str(name, default=""):
    value = os.getenv(name)
    if value is None:
        return default
    return value


def env_int(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def setup_logging():
    level_name = env_str("APP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_logger(name):
    return logging.getLogger(name)


def api_response(ok, data=None, error=None, code="OK", request_id="", meta=None):
    return {
        "ok": ok,
        "code": code,
        "request_id": request_id,
        "data": data if data is not None else {},
        "error": error,
        "meta": meta or {},
    }

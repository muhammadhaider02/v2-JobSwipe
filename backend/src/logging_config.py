import logging
import os
import sys

_configured = False


def setup_logging():
    global _configured
    if _configured:
        return
    _configured = True

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


setup_logging()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def redact_uid(user_id: str | None) -> str:
    if not user_id:
        return "<none>"
    return f"{user_id[:8]}..."

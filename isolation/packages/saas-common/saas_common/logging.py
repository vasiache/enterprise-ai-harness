"""Structured JSON logging via structlog.

Usage:
    from saas_common.logging import get_logger

    log = get_logger(__name__)
    log.info("agent.invoke", tenant_id=tid, user_id=uid, input_len=len(text))

All log records include: timestamp, level, logger, tenant_id (if bound).
"""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Call once at application startup (before any log.* calls)."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog logger bound to `name`."""
    return structlog.get_logger(name)


def bind_tenant(tenant_id: str, org: str = "") -> None:
    """Bind tenant_id (and optionally org) to the current async context.

    Call this at request entry so every subsequent log in the same
    coroutine includes these fields automatically.
    """
    structlog.contextvars.bind_contextvars(tenant_id=tenant_id, org=org)


def clear_context() -> None:
    """Clear bound context vars - call at request teardown."""
    structlog.contextvars.clear_contextvars()

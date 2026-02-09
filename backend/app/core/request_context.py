from contextvars import ContextVar
from typing import Any

_auth_context: ContextVar[dict[str, Any] | None] = ContextVar("auth_context", default=None)


def set_auth_context(data: dict[str, Any]) -> None:
    _auth_context.set(dict(data))


def get_auth_context() -> dict[str, Any] | None:
    return _auth_context.get()


def clear_auth_context() -> None:
    _auth_context.set(None)

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException
from pydantic import ValidationError

from cys_core.domain.persistence.exceptions import PersistenceUnavailableError
from interfaces.api.llm_errors import is_llm_error, raise_llm_unavailable


def raise_run_api_error(exc: BaseException) -> NoReturn:
    """Map run/session exceptions to structured HTTP errors."""
    if is_llm_error(exc):
        raise_llm_unavailable(exc)
    if isinstance(exc, PersistenceUnavailableError):
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "code": "persistence_unavailable"},
        ) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "code": "unknown_resource"},
        ) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "code": "validation_error"},
        ) from exc
    if isinstance(exc, RuntimeError):
        message = str(exc).lower()
        if "persistence" in message or "agent definitions loader" in message:
            raise HTTPException(
                status_code=503,
                detail={"message": str(exc), "code": "persistence_unavailable"},
            ) from exc
    raise exc

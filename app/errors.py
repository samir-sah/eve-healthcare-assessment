from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class ApiError(HTTPException):
    """Stable, secret-safe API error envelope used by routes and services."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        body: dict[str, Any] = {"code": code, "message": message}
        if details:
            body["details"] = details
        super().__init__(status_code=status_code, detail=body)

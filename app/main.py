from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import ApiError
from app.routes import auth, catalogue

SessionDependency = Annotated[Session, Depends(get_session)]


def error_response(
    status_code: int, code: str, message: str, details: object | None = None
) -> JSONResponse:
    body: dict[str, object] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def create_app() -> FastAPI:
    app = FastAPI(
        title="EVE Healthcare Booking API",
        version="0.1.0",
        description="Diagnostic-test booking service with simulated payments.",
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(
            exc.status_code, exc.detail["code"], exc.detail["message"], exc.detail.get("details")
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"] if part != "body"),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return error_response(422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.get("/health/", tags=["health"])
    def health_check(session: SessionDependency) -> dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return error_response(503, "DATABASE_UNAVAILABLE", "Database is unavailable")
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(catalogue.router)

    return app


app = create_app()

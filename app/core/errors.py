from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error mapped to a JSON response."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MarketDataError(AppError):
    status_code = 502
    code = "market_data_error"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.code, "message": exc.message}},
    )

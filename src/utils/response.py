from __future__ import annotations

from typing import Any, Optional

from fastapi.responses import JSONResponse


def success(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> JSONResponse:
    payload: dict[str, Any] = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return JSONResponse(content=payload, status_code=status_code)


def created(data: Any = None, message: str = "Created") -> JSONResponse:
    return success(data=data, message=message, status_code=201)


def error(
    message: str,
    code: int,
    status_code: int,
    details: Optional[Any] = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(content=payload, status_code=status_code)

"""FastAPI dependency: extract and validate the current user from JWT."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict[str, Any]:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise exc

    customer_id: str | None = payload.get("sub")
    if not customer_id:
        raise exc

    return {
        "customer_id": customer_id,
        "email": payload.get("email", ""),
        "name": payload.get("name", ""),
    }

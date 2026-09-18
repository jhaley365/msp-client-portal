"""FastAPI dependency: extract and validate the current user from JWT."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    x_view_as_customer: str | None = Header(default=None),
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

    is_admin: bool = bool(payload.get("is_admin", False))

    # Admins may pass X-View-As-Customer to impersonate any customer.
    effective_customer_id = customer_id
    if is_admin and x_view_as_customer:
        effective_customer_id = x_view_as_customer

    return {
        "customer_id": effective_customer_id,
        "email": payload.get("email", ""),
        "name": payload.get("name", ""),
        "is_admin": is_admin,
    }

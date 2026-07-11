"""Admin-only endpoints: customer list + user management."""

from __future__ import annotations

from typing import Any

import boto3
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user
from app.services.user_service import create_user, get_user_by_id, list_users, update_user

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _customers_table() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table("Customers")


# ---------------------------------------------------------------------------
# Customers (org list for the switcher)
# ---------------------------------------------------------------------------

@router.get("/customers")
def list_customers(user: dict = Depends(_require_admin)) -> list[dict]:
    tbl = _customers_table()
    items: list[dict] = []
    kwargs: dict[str, Any] = {
        "ProjectionExpression": "customer_id, #n, #h",
        "ExpressionAttributeNames": {"#n": "name", "#h": "hidden"},
    }
    while True:
        resp = tbl.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    visible = [i for i in items if not i.get("hidden")]
    return sorted(visible, key=lambda x: (x.get("name") or x.get("customer_id", "")).lower())


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = ""
    customer_id: str
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    name: str | None = None
    customer_id: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


@router.get("/users")
def admin_list_users(user: dict = Depends(_require_admin)) -> list[dict]:
    return list_users()


@router.post("/users", status_code=201)
def admin_create_user(body: CreateUserRequest, user: dict = Depends(_require_admin)) -> dict:
    try:
        return create_user(
            email=body.email,
            customer_id=body.customer_id,
            name=body.name,
            is_admin=body.is_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.patch("/users/{user_id}")
def admin_update_user(
    user_id: str,
    body: UpdateUserRequest,
    user: dict = Depends(_require_admin),
) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    result = update_user(user_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.delete("/users/{user_id}")
def admin_deactivate_user(user_id: str, user: dict = Depends(_require_admin)) -> dict:
    target = get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    update_user(user_id, is_active=False)
    return {"ok": True}

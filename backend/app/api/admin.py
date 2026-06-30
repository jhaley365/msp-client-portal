"""Admin-only endpoints."""

from __future__ import annotations

from typing import Any

import boto3
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

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


@router.get("/customers")
def list_customers(user: dict = Depends(_require_admin)) -> list[dict]:
    """Return all customer records (id + name only) for the admin switcher."""
    tbl = _customers_table()
    items: list[dict] = []
    kwargs: dict[str, Any] = {
        "ProjectionExpression": "customer_id, #n, hidden",
        "ExpressionAttributeNames": {"#n": "name"},
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

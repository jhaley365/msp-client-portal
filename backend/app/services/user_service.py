"""
User management — separate from the Customers org table.

DynamoDB table: Users
    PK:  user_id  (UUID)
    GSI: email-index  (email → user_id)

Each user belongs to one customer org (customer_id FK → Customers table).
Multiple users can share the same customer_id.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
TABLE_USERS = "Users"
EMAIL_INDEX = "email-index"


def _table() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs).Table(TABLE_USERS)


def get_user_by_email(email: str) -> dict | None:
    try:
        resp = _table().query(
            IndexName=EMAIL_INDEX,
            KeyConditionExpression=Key("email").eq(email.lower().strip()),
            Limit=1,
        )
        items = resp.get("Items", [])
        return items[0] if items else None
    except ClientError as exc:
        logger.error("Error querying user by email: %s", exc)
        raise


def get_user_by_id(user_id: str) -> dict | None:
    resp = _table().get_item(Key={"user_id": user_id})
    return resp.get("Item")


def list_users() -> list[dict]:
    tbl = _table()
    items: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = tbl.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return sorted(items, key=lambda x: (x.get("name") or x.get("email", "")).lower())


def create_user(
    email: str,
    customer_id: str,
    name: str = "",
    is_admin: bool = False,
) -> dict:
    existing = get_user_by_email(email)
    if existing:
        raise ValueError(f"Email already registered: {email}")

    user_id = str(uuid.uuid4())
    item = {
        "user_id": user_id,
        "email": email.lower().strip(),
        "customer_id": customer_id,
        "name": name,
        "is_admin": is_admin,
        "is_active": True,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    _table().put_item(Item=item, ConditionExpression="attribute_not_exists(user_id)")
    logger.info("Created user %s (%s) for customer %s", user_id, email, customer_id)
    return item


def update_user(user_id: str, **kwargs: Any) -> dict | None:
    allowed = {"name", "is_admin", "is_active", "customer_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_user_by_id(user_id)

    set_expr = ", ".join(f"#{k} = :{k}" for k in updates)
    resp = _table().update_item(
        Key={"user_id": user_id},
        UpdateExpression=f"SET {set_expr}",
        ExpressionAttributeNames={f"#{k}": k for k in updates},
        ExpressionAttributeValues={f":{k}": v for k, v in updates.items()},
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes")

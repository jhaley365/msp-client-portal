"""Office 365 endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/o365", tags=["o365"])

TABLE_LICENSES = "O365Licenses"
TABLE_MAILBOXES = "O365Mailboxes"

# SKUs that are infrastructure/noise and not useful to display
_HIDDEN_SKUS = {
    "FLOW_FREE",
    "WINDOWS_STORE",
    "MICROSOFT_FLOW_FREE",
    "POWER_BI_STANDARD",
}


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    """Return license and mailbox totals for the O365 dashboard card."""
    customer_id: str = user["customer_id"]

    tbl_licenses = _table(TABLE_LICENSES)
    tbl_mailboxes = _table(TABLE_MAILBOXES)

    # Fetch all license records so we can sum unit counts.
    license_resp = tbl_licenses.query(
        IndexName="customer_id-index",
        KeyConditionExpression=Key("customer_id").eq(customer_id),
    )
    license_items = [
        i for i in license_resp.get("Items", [])
        if i.get("sku_name", "") not in _HIDDEN_SKUS
        and int(i.get("total_units", 0)) < 10000
    ]

    total_licenses = sum(int(item.get("total_units", 0)) for item in license_items)
    consumed_licenses = sum(int(item.get("consumed_units", 0)) for item in license_items)
    available_licenses = sum(int(item.get("available_units", 0)) for item in license_items)

    # Count total mailboxes.
    mailbox_resp = tbl_mailboxes.query(
        IndexName="customer_id-last_synced_at-index",
        KeyConditionExpression=Key("customer_id").eq(customer_id),
        Select="COUNT",
    )
    total_mailboxes = mailbox_resp.get("Count", 0)

    return {
        "total_licenses": total_licenses,
        "consumed_licenses": consumed_licenses,
        "available_licenses": available_licenses,
        "total_mailboxes": total_mailboxes,
    }


# ── Licenses ──────────────────────────────────────────────────────────────────


@router.get("/licenses")
def list_licenses(user: dict = Depends(get_current_user)) -> dict:
    """Return all O365 license SKUs for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_LICENSES)

    resp = tbl.query(
        IndexName="customer_id-index",
        KeyConditionExpression=Key("customer_id").eq(customer_id),
    )

    items = [
        i for i in resp.get("Items", [])
        if i.get("sku_name", "") not in _HIDDEN_SKUS
        and int(i.get("total_units", 0)) < 10000
    ]
    return {
        "items": items,
        "count": len(items),
    }


# ── Mailboxes ─────────────────────────────────────────────────────────────────


@router.get("/mailboxes")
def list_mailboxes(user: dict = Depends(get_current_user)) -> dict:
    """Return all O365 mailboxes for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_MAILBOXES)

    items: list[dict] = []
    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-last_synced_at-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "ScanIndexForward": False,
    }
    while True:
        resp = tbl.query(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    return {"items": items, "count": len(items)}

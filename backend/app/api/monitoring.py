"""CheckMK monitoring endpoints — host status and service problems, scoped to the authenticated customer."""

from __future__ import annotations

import base64
import json
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_PAGE_SIZE = 50

TABLE_HOSTS = "CheckMKHosts"
TABLE_SERVICES = "CheckMKServices"
GSI_NAME = "customer_id-last_synced_at-index"


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


def _encode_key(last_evaluated_key: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(last_evaluated_key).encode()).decode()


def _decode_key(token: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(token.encode()))


def _query_all_for_customer(table_name: str, customer_id: str) -> list[dict]:
    """Fetch all items for a customer via GSI (no pagination limit)."""
    tbl = _table(table_name)
    items: list[dict] = []
    kwargs: dict[str, Any] = {
        "IndexName": GSI_NAME,
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
    }
    while True:
        resp = tbl.query(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def _query_customer_paged(
    table_name: str,
    customer_id: str,
    last_key: str | None,
) -> dict[str, Any]:
    tbl = _table(table_name)
    kwargs: dict[str, Any] = {
        "IndexName": GSI_NAME,
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        try:
            kwargs["ExclusiveStartKey"] = _decode_key(last_key)
        except Exception:
            pass

    resp = tbl.query(**kwargs)
    lek = resp.get("LastEvaluatedKey")
    return {
        "items": resp.get("Items", []),
        "next_key": _encode_key(lek) if lek else None,
        "count": resp.get("Count", 0),
    }


# ── Summary ───────────────────────────────────────────────────────────────────


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    customer_id: str = user["customer_id"]

    hosts = _query_all_for_customer(TABLE_HOSTS, customer_id)
    services = _query_all_for_customer(TABLE_SERVICES, customer_id)

    hosts_up = sum(1 for h in hosts if h.get("status") == "Up")
    hosts_down = sum(1 for h in hosts if h.get("status") == "Down")
    hosts_unreachable = sum(1 for h in hosts if h.get("status") == "Unreachable")
    hosts_pending = sum(1 for h in hosts if h.get("status") == "Pending")

    services_warn = sum(1 for s in services if s.get("status") == "Warn")
    services_crit = sum(1 for s in services if s.get("status") == "Crit")
    services_unknown = sum(1 for s in services if s.get("status") == "Unknown")

    return {
        "hosts_up": hosts_up,
        "hosts_down": hosts_down,
        "hosts_unreachable": hosts_unreachable,
        "hosts_pending": hosts_pending,
        "services_warn": services_warn,
        "services_crit": services_crit,
        "services_unknown": services_unknown,
        "total_hosts": len(hosts),
        "total_services": len(services),
    }


# ── Hosts ─────────────────────────────────────────────────────────────────────


@router.get("/hosts")
def hosts(
    next_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    customer_id: str = user["customer_id"]
    result = _query_customer_paged(TABLE_HOSTS, customer_id, next_key)
    # Sort by host_name client-side within the page
    result["items"] = sorted(result["items"], key=lambda h: h.get("host_name", "").lower())
    return result


# ── Problems ──────────────────────────────────────────────────────────────────

_PROBLEM_STATE_ORDER = {"Crit": 0, "Down": 1, "Unreachable": 2, "Warn": 3, "Unknown": 4}


@router.get("/problems")
def problems(user: dict = Depends(get_current_user)) -> dict:
    customer_id: str = user["customer_id"]
    services = _query_all_for_customer(TABLE_SERVICES, customer_id)

    # Filter to non-OK
    non_ok = [s for s in services if s.get("status") != "Ok"]

    # Sort: crit first, then by host_name
    non_ok.sort(
        key=lambda s: (
            _PROBLEM_STATE_ORDER.get(s.get("status", ""), 99),
            s.get("host_name", "").lower(),
        )
    )

    return {"items": non_ok, "count": len(non_ok)}

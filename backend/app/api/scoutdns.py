"""ScoutDNS endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

import json
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/scoutdns", tags=["scoutdns"])

_PAGE_SIZE = 100

TABLE_SUMMARY = "ScoutDNSSummary"
TABLE_SITES = "ScoutDNSSites"
TABLE_CLIENTS = "ScoutDNSClients"


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


def _int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    """Return pre-aggregated DNS summary for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_SUMMARY)

    resp = tbl.get_item(Key={"customer_id": customer_id})
    item = resp.get("Item")
    if not item:
        return {
            "allowed_requests": 0,
            "blocked_requests": 0,
            "threat_count": 0,
            "online_clients": 0,
            "offline_clients": 0,
            "top_categories": [],
            "top_domains": [],
            "period": "Last 30 Days",
            "last_synced_at": None,
        }

    top_categories = item.get("top_categories", "[]")
    top_domains = item.get("top_domains", "[]")
    try:
        top_categories = json.loads(top_categories) if isinstance(top_categories, str) else top_categories
    except (json.JSONDecodeError, TypeError):
        top_categories = []
    try:
        top_domains = json.loads(top_domains) if isinstance(top_domains, str) else top_domains
    except (json.JSONDecodeError, TypeError):
        top_domains = []

    return {
        "allowed_requests": _int(item.get("allowed_requests", 0)),
        "blocked_requests": _int(item.get("blocked_requests", 0)),
        "threat_count": _int(item.get("threat_count", 0)),
        "online_clients": _int(item.get("online_clients", 0)),
        "offline_clients": _int(item.get("offline_clients", 0)),
        "top_categories": top_categories,
        "top_domains": top_domains,
        "period": item.get("period", "Last 30 Days"),
        "last_synced_at": item.get("last_synced_at"),
    }


# ── Sites ─────────────────────────────────────────────────────────────────────


@router.get("/sites")
def list_sites(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return network sites (locations) for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_SITES)

    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
    }
    if last_key:
        kwargs["ExclusiveStartKey"] = {"customer_id": customer_id, "site_id": last_key}

    resp = tbl.query(**kwargs)
    return {
        "items": resp.get("Items", []),
        "next_key": resp.get("LastEvaluatedKey", {}).get("site_id"),
        "count": resp.get("Count", 0),
    }


# ── Clients ───────────────────────────────────────────────────────────────────


@router.get("/clients")
def list_clients(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return roaming clients for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_CLIENTS)

    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
    }
    if last_key:
        kwargs["ExclusiveStartKey"] = {"customer_id": customer_id, "client_id": last_key}

    resp = tbl.query(**kwargs)
    return {
        "items": resp.get("Items", []),
        "next_key": resp.get("LastEvaluatedKey", {}).get("client_id"),
        "count": resp.get("Count", 0),
    }

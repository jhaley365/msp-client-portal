"""ScoutDNS stats endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/scoutdns", tags=["scoutdns"])

_PAGE_SIZE = 50

TABLE_STATS = "ScoutDNSStats"


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


def _today_utc() -> date:
    return datetime.now(tz=timezone.utc).date()


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary")
def summary(
    days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return aggregated DNS query totals for the last *days* days.

    Parameters
    ----------
    days:
        Number of past days to aggregate (default 30, max 365).
    """
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_STATS)

    cutoff_date = (_today_utc() - timedelta(days=days)).isoformat()

    resp = tbl.query(
        IndexName="customer_id-date-index",
        KeyConditionExpression=(
            Key("customer_id").eq(customer_id) & Key("date").gte(cutoff_date)
        ),
        ScanIndexForward=False,
    )

    items = resp.get("Items", [])

    total_queries = sum(int(item.get("total_queries", 0)) for item in items)
    blocked_queries = sum(int(item.get("blocked_queries", 0)) for item in items)
    allowed_queries = sum(int(item.get("allowed_queries", 0)) for item in items)

    block_rate: float = (
        round(blocked_queries / total_queries * 100, 2) if total_queries > 0 else 0.0
    )

    return {
        "days": days,
        "total_queries": total_queries,
        "blocked_queries": blocked_queries,
        "allowed_queries": allowed_queries,
        "block_rate_pct": block_rate,
    }


# ── Stats list ────────────────────────────────────────────────────────────────


@router.get("/stats")
def list_stats(
    days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return daily ScoutDNS stat records sorted by date descending.

    Parameters
    ----------
    days:
        Number of past days to return (default 30, max 365).
    """
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_STATS)

    cutoff_date = (_today_utc() - timedelta(days=days)).isoformat()

    resp = tbl.query(
        IndexName="customer_id-date-index",
        KeyConditionExpression=(
            Key("customer_id").eq(customer_id) & Key("date").gte(cutoff_date)
        ),
        ScanIndexForward=False,
    )

    return {
        "items": resp.get("Items", []),
        "count": resp.get("Count", 0),
    }

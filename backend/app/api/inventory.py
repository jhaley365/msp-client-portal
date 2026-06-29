"""EC2 inventory endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/inventory", tags=["inventory"])

_PAGE_SIZE = 50


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


def _query_customer(
    table_name: str,
    index_name: str,
    customer_id: str,
    last_key: str | None,
) -> dict[str, Any]:
    tbl = _table(table_name)
    kwargs: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        kwargs["ExclusiveStartKey"] = {"customer_id": customer_id, "last_synced_at": last_key}

    resp = tbl.query(**kwargs)
    return {
        "items": resp.get("Items", []),
        "next_key": resp.get("LastEvaluatedKey", {}).get("last_synced_at"),
        "count": resp.get("Count", 0),
    }


# ── Summary ──────────────────────────────────────────────────────────────────

@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    """Return counts of instances, volumes and snapshots for the dashboard."""
    customer_id = user["customer_id"]

    def count(table_name: str, index: str) -> int:
        tbl = _table(table_name)
        resp = tbl.query(
            IndexName=index,
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    return {
        "instances": count("EC2Instances", "customer_id-last_synced_at-index"),
        "volumes": count("EC2Volumes", "customer_id-last_synced_at-index"),
        "snapshots": count("EC2Snapshots", "customer_id-start_time-index"),
    }


# ── Instances ─────────────────────────────────────────────────────────────────

@router.get("/instances")
def list_instances(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "EC2Instances",
        "customer_id-last_synced_at-index",
        user["customer_id"],
        last_key,
    )
    result["items"] = sorted(
        result["items"],
        key=lambda x: (x.get("name_tag") or "").lower(),
    )
    return result


# ── Volumes ───────────────────────────────────────────────────────────────────

@router.get("/volumes")
def list_volumes(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    return _query_customer(
        "EC2Volumes",
        "customer_id-last_synced_at-index",
        user["customer_id"],
        last_key,
    )


# ── Snapshots ─────────────────────────────────────────────────────────────────

@router.get("/snapshots")
def list_snapshots(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    tbl = _table("EC2Snapshots")
    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-start_time-index",
        "KeyConditionExpression": Key("customer_id").eq(user["customer_id"]),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        kwargs["ExclusiveStartKey"] = {
            "customer_id": user["customer_id"],
            "start_time": last_key,
        }
    resp = tbl.query(**kwargs)
    return {
        "items": resp.get("Items", []),
        "next_key": resp.get("LastEvaluatedKey", {}).get("start_time"),
        "count": resp.get("Count", 0),
    }

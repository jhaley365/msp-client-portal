"""Huntress endpoints — all scoped to the authenticated customer."""

from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/huntress", tags=["huntress"])

_PAGE_SIZE = 50

TABLE_AGENTS = "HuntressAgents"
TABLE_INCIDENTS = "HuntressIncidents"


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    """Return agent and incident counts for the Huntress dashboard card."""
    customer_id: str = user["customer_id"]

    tbl_agents = _table(TABLE_AGENTS)
    tbl_incidents = _table(TABLE_INCIDENTS)

    def _count_agents_total() -> int:
        resp = tbl_agents.query(
            IndexName="customer_id-last_synced_at-index",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    def _count_agents_by_status(status_value: str) -> int:
        resp = tbl_agents.query(
            IndexName="customer_id-status-index",
            KeyConditionExpression=(
                Key("customer_id").eq(customer_id) & Key("status").eq(status_value)
            ),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    def _count_incidents_total() -> int:
        resp = tbl_incidents.query(
            IndexName="customer_id-created_at-index",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    def _count_incidents_by_severity(severity_value: str) -> int:
        resp = tbl_incidents.query(
            IndexName="customer_id-severity-index",
            KeyConditionExpression=(
                Key("customer_id").eq(customer_id)
                & Key("severity").eq(severity_value)
            ),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    def _count_open_incidents() -> int:
        # HuntressIncidents does not have a status GSI; scan-filter is
        # acceptable for summary counts given expected data volumes.
        from boto3.dynamodb.conditions import Attr

        resp = tbl_incidents.query(
            IndexName="customer_id-created_at-index",
            KeyConditionExpression=Key("customer_id").eq(customer_id),
            FilterExpression=Attr("status").eq("open"),
            Select="COUNT",
        )
        return resp.get("Count", 0)

    return {
        "total_agents": _count_agents_total(),
        "online_agents": _count_agents_by_status("online"),
        "total_incidents": _count_incidents_total(),
        "open_incidents": _count_open_incidents(),
        "critical_incidents": _count_incidents_by_severity("critical"),
    }


# ── Agents ────────────────────────────────────────────────────────────────────


@router.get("/agents")
def list_agents(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return a paginated list of Huntress agents for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_AGENTS)

    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-last_synced_at-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        kwargs["ExclusiveStartKey"] = {
            "customer_id": customer_id,
            "last_synced_at": last_key,
            "agent_id": last_key,
        }

    resp = tbl.query(**kwargs)
    return {
        "items": resp.get("Items", []),
        "next_key": resp.get("LastEvaluatedKey", {}).get("last_synced_at"),
        "count": resp.get("Count", 0),
    }


# ── Incidents ─────────────────────────────────────────────────────────────────


@router.get("/incidents")
def list_incidents(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    """Return a paginated list of Huntress incidents for the authenticated customer."""
    customer_id: str = user["customer_id"]
    tbl = _table(TABLE_INCIDENTS)

    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-created_at-index",
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        kwargs["ExclusiveStartKey"] = {
            "customer_id": customer_id,
            "created_at": last_key,
            "incident_id": last_key,
        }

    resp = tbl.query(**kwargs)
    return {
        "items": resp.get("Items", []),
        "next_key": resp.get("LastEvaluatedKey", {}).get("created_at"),
        "count": resp.get("Count", 0),
    }

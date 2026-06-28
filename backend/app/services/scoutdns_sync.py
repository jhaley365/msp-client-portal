"""
AWS Lambda — ScoutDNS Stats Sync
==================================
Fetches daily DNS statistics from the ScoutDNS API for each organization,
maps each organization to a portal customer via name lookup, and upserts
the data into the ScoutDNSStats DynamoDB table.

Invoke schedule (recommended): EventBridge rule once daily (after midnight UTC).

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:Scan             (Customers)
    dynamodb:PutItem          (ScoutDNSStats)
    dynamodb:BatchWriteItem   (ScoutDNSStats)

Environment variables
---------------------
    SCOUTDNS_API_KEY     ScoutDNS API key (used as Bearer token)
    DYNAMODB_REGION      AWS region where DynamoDB tables live (default: us-east-1)
    DYNAMODB_ENDPOINT_URL  Override endpoint for local testing (e.g. DynamoDB Local)
    SCOUTDNS_DAYS_BACK   Number of past days to sync per org (default: 1)

Notes
-----
The ScoutDNS API base URL and exact endpoint paths are placeholders.
Search for ``# TODO`` comments to find sections that need updating once
the real API documentation is available.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOUTDNS_API_KEY: str = os.environ.get("SCOUTDNS_API_KEY", "")
# TODO: Replace with the real ScoutDNS API base URL once confirmed.
SCOUTDNS_BASE_URL = "https://api.scoutdns.com/v1"

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
_DAYS_BACK: int = int(os.environ.get("SCOUTDNS_DAYS_BACK", "1"))

TABLE_STATS = "ScoutDNSStats"
TABLE_CUSTOMERS = "Customers"

_BATCH_SIZE = 25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dynamo_resource() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _today_utc() -> date:
    return datetime.now(tz=timezone.utc).date()


def _batch_write(table: Any, items: list[dict]) -> None:
    """Write items in batches of 25, retrying unprocessed items once."""
    for i in range(0, len(items), _BATCH_SIZE):
        chunk = items[i : i + _BATCH_SIZE]
        requests_list = [{"PutRequest": {"Item": item}} for item in chunk]
        response = table.meta.client.batch_write_item(
            RequestItems={table.name: requests_list}
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _scoutdns_session() -> requests.Session:
    """Return a requests Session pre-configured with ScoutDNS Bearer auth."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {SCOUTDNS_API_KEY}",
            "Accept": "application/json",
        }
    )
    return session


# ---------------------------------------------------------------------------
# Customer name cache
# ---------------------------------------------------------------------------


class CustomerNameCache:
    """Lazy cache: resolves an organization name → (customer_id, customer_name).

    Scans the Customers DynamoDB table once on first miss and builds an
    in-memory map keyed by the ``name`` field for subsequent lookups.
    """

    def __init__(self, customers_table: Any) -> None:
        self._table = customers_table
        self._cache: dict[str, tuple[str, str]] | None = None

    def _load(self) -> None:
        """Scan the Customers table and populate the cache."""
        self._cache = {}
        kwargs: dict[str, Any] = {}
        while True:
            resp = self._table.scan(**kwargs)
            for item in resp.get("Items", []):
                name: str = item.get("name", "")
                cid: str = item.get("customer_id", "")
                if name and cid:
                    self._cache[name.lower()] = (cid, name)
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
        logger.info("CustomerNameCache loaded %d entries", len(self._cache))

    def resolve(self, org_name: str) -> tuple[str, str] | None:
        """Return ``(customer_id, customer_name)`` for the given org name.

        Returns ``None`` when no matching customer is found.
        """
        if self._cache is None:
            self._load()
        result = self._cache.get(org_name.lower())  # type: ignore[union-attr]
        if result is None:
            logger.warning("No customer found for ScoutDNS org name: %s", org_name)
        return result


# ---------------------------------------------------------------------------
# ScoutDNS API calls
# ---------------------------------------------------------------------------


def _fetch_organizations(session: requests.Session) -> list[dict]:
    """Return all ScoutDNS organizations.

    # TODO: Confirm the exact endpoint path and response shape.
    # Expected response: [{"id": "...", "name": "..."}, ...]
    """
    # TODO: Replace with real endpoint once API docs are confirmed.
    url = f"{SCOUTDNS_BASE_URL}/organizations"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()  # TODO: confirm response key; may be {"orgs": [...]}
    except requests.RequestException as exc:
        logger.error("ScoutDNS API error fetching organizations: %s", exc)
        return []


def _fetch_summary(
    session: requests.Session,
    org_id: str,
    report_date: str,
) -> dict:
    """Return total_queries, blocked_queries, allowed_queries for an org/date.

    # TODO: Confirm the exact endpoint path, query parameters, and response shape.
    """
    # TODO: Replace with real endpoint once API docs are confirmed.
    url = f"{SCOUTDNS_BASE_URL}/reports/summary"
    params = {"org_id": org_id, "date": report_date}
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()  # TODO: confirm keys match total_queries / blocked_queries / allowed_queries
    except requests.RequestException as exc:
        logger.error(
            "ScoutDNS API error fetching summary for org %s date %s: %s",
            org_id,
            report_date,
            exc,
        )
        return {}


def _fetch_top_blocked(
    session: requests.Session,
    org_id: str,
    report_date: str,
    limit: int = 10,
) -> list[str]:
    """Return the top blocked domain names for an org/date.

    # TODO: Confirm the exact endpoint path, query parameters, and response shape.
    """
    # TODO: Replace with real endpoint once API docs are confirmed.
    url = f"{SCOUTDNS_BASE_URL}/reports/top_blocked"
    params = {"org_id": org_id, "date": report_date, "limit": limit}
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # TODO: confirm response key; may be {"domains": ["example.com", ...]}
        domains = data if isinstance(data, list) else data.get("domains", [])
        return [str(d) for d in domains]
    except requests.RequestException as exc:
        logger.error(
            "ScoutDNS API error fetching top_blocked for org %s date %s: %s",
            org_id,
            report_date,
            exc,
        )
        return []


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    """Entry point invoked by EventBridge or a manual test event."""
    synced_at = _utcnow_iso()
    logger.info("Starting ScoutDNS stats sync at %s", synced_at)

    dynamo = _dynamo_resource()
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)
    tbl_stats = dynamo.Table(TABLE_STATS)

    cache = CustomerNameCache(tbl_customers)
    session = _scoutdns_session()

    orgs = _fetch_organizations(session)
    logger.info("Fetched %d ScoutDNS organization(s)", len(orgs))

    today = _today_utc()
    dates_to_sync = [
        (today - timedelta(days=d)).isoformat() for d in range(_DAYS_BACK)
    ]

    stat_items: list[dict] = []

    for org in orgs:
        # TODO: confirm the org dict field names (may be "id" / "name" or "org_id" / "org_name").
        org_id: str = str(org.get("id", ""))
        org_name: str = org.get("name", "")

        resolved = cache.resolve(org_name) if org_name else None
        customer_id = resolved[0] if resolved else "unassigned"
        customer_name = resolved[1] if resolved else org_name

        for report_date in dates_to_sync:
            summary = _fetch_summary(session, org_id, report_date)
            top_blocked = _fetch_top_blocked(session, org_id, report_date)

            total_queries: int = int(summary.get("total_queries", 0))
            blocked_queries: int = int(summary.get("blocked_queries", 0))
            allowed_queries: int = int(summary.get("allowed_queries", 0))

            stat_id = f"{customer_id}#{report_date}"

            item: dict[str, Any] = {
                "stat_id": stat_id,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "date": report_date,
                "total_queries": total_queries,
                "blocked_queries": blocked_queries,
                "allowed_queries": allowed_queries,
                "top_blocked_domains": top_blocked,
                "last_synced_at": synced_at,
            }
            stat_items.append(item)
            logger.debug(
                "Built stat item %s: total=%d blocked=%d",
                stat_id,
                total_queries,
                blocked_queries,
            )

    if stat_items:
        _batch_write(tbl_stats, stat_items)

    totals = {"stats_upserted": len(stat_items)}
    logger.info("ScoutDNS sync complete. Upserted: %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

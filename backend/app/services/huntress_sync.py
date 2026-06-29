"""
AWS Lambda — Huntress Sync
===========================
Fetches Huntress agents and incidents via the Huntress REST API, maps each
record to a portal customer via the organization name, then upserts the data
into the HuntressAgents and HuntressIncidents DynamoDB tables.

Invoke schedule (recommended): EventBridge rule every 15–60 minutes.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:Scan             (Customers)
    dynamodb:PutItem          (HuntressAgents, HuntressIncidents)
    dynamodb:BatchWriteItem   (HuntressAgents, HuntressIncidents)

Environment variables
---------------------
    HUNTRESS_API_KEY     Huntress API key
    HUNTRESS_API_SECRET  Huntress API secret
    DYNAMODB_REGION      AWS region where DynamoDB tables live (default: us-east-1)
    DYNAMODB_ENDPOINT_URL  Override endpoint for local testing (e.g. DynamoDB Local)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HUNTRESS_API_KEY: str = os.environ.get("HUNTRESS_API_KEY", "")
HUNTRESS_API_SECRET: str = os.environ.get("HUNTRESS_API_SECRET", "")
HUNTRESS_BASE_URL = "https://api.huntress.io/v1"

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

TABLE_AGENTS = "HuntressAgents"
TABLE_INCIDENTS = "HuntressIncidents"
TABLE_CUSTOMERS = "Customers"

_BATCH_SIZE = 25
_PAGE_LIMIT = 500


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
            # Single retry for unprocessed items.
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _huntress_session() -> requests.Session:
    """Return a requests Session pre-configured with Huntress Basic auth."""
    session = requests.Session()
    session.auth = (HUNTRESS_API_KEY, HUNTRESS_API_SECRET)
    session.headers.update({"Accept": "application/json"})
    return session


def _paginate_huntress(
    session: requests.Session,
    endpoint: str,
    result_key: str,
) -> list[dict]:
    """Paginate through a Huntress API endpoint and collect all records.

    Parameters
    ----------
    session:
        Authenticated requests Session.
    endpoint:
        API path relative to HUNTRESS_BASE_URL (e.g. ``"/agents"``).
    result_key:
        Key in the JSON response that contains the list of records
        (e.g. ``"agents"`` or ``"incidents"``).

    Returns
    -------
    list[dict]
        All records across all pages.
    """
    items: list[dict] = []
    page = 1

    while True:
        url = f"{HUNTRESS_BASE_URL}{endpoint}"
        params = {"page": page, "limit": _PAGE_LIMIT}
        try:
            resp = session.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(
                "Huntress API error fetching %s page %d: %s", endpoint, page, exc
            )
            break

        data = resp.json()
        page_items = data.get(result_key, [])
        items.extend(page_items)

        logger.debug(
            "Huntress %s page %d: %d records (total so far: %d)",
            endpoint,
            page,
            len(page_items),
            len(items),
        )

        # Huntress pagination: stop when a page returns fewer items than the limit.
        if len(page_items) < _PAGE_LIMIT:
            break
        page += 1

    return items


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
        # Map lowercase organization name → (customer_id, customer_name)
        self._cache: dict[str, tuple[str, str]] | None = None

    def _load(self) -> None:
        """Scan the Customers table and populate the cache.

        Prefers the ``huntress_org_name`` field for matching; falls back to
        ``name`` when that field is absent.
        """
        self._cache = {}
        kwargs: dict[str, Any] = {}
        while True:
            resp = self._table.scan(**kwargs)
            for item in resp.get("Items", []):
                cid: str = item.get("customer_id", "")
                display_name: str = item.get("name", "")
                # huntress_org_name takes precedence for matching.
                match_name: str = item.get("huntress_org_name") or display_name
                if match_name and cid:
                    self._cache[match_name.lower()] = (cid, display_name or match_name)
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
            logger.warning("No customer found for Huntress org name: %s", org_name)
        return result


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    """Entry point invoked by EventBridge or a manual test event."""
    synced_at = _utcnow_iso()
    logger.info("Starting Huntress sync at %s", synced_at)

    dynamo = _dynamo_resource()
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)
    tbl_agents = dynamo.Table(TABLE_AGENTS)
    tbl_incidents = dynamo.Table(TABLE_INCIDENTS)

    cache = CustomerNameCache(tbl_customers)
    session = _huntress_session()

    # ── Agents ────────────────────────────────────────────────────────────────

    raw_agents = _paginate_huntress(session, "/agents", "agents")
    logger.info("Fetched %d Huntress agents", len(raw_agents))

    agent_items: list[dict] = []
    for agent in raw_agents:
        org_name: str = agent.get("organization_name", "")
        resolved = cache.resolve(org_name) if org_name else None
        customer_id = resolved[0] if resolved else "unassigned"
        customer_name = resolved[1] if resolved else org_name

        item: dict[str, Any] = {
            "agent_id": str(agent.get("id", "")),
            "customer_id": customer_id,
            "customer_name": customer_name,
            "hostname": agent.get("hostname", ""),
            "platform": agent.get("platform", ""),
            "policy_name": agent.get("policy_name", ""),
            "status": agent.get("status", ""),
            "last_seen_at": agent.get("last_seen_at", ""),
            "version": agent.get("version", ""),
            "last_synced_at": synced_at,
        }
        agent_items.append(item)

    if agent_items:
        _batch_write(tbl_agents, agent_items)

    # ── Incidents ─────────────────────────────────────────────────────────────

    raw_incidents = _paginate_huntress(session, "/incidents", "incidents")
    logger.info("Fetched %d Huntress incidents", len(raw_incidents))

    incident_items: list[dict] = []
    for incident in raw_incidents:
        org_name = incident.get("organization_name", "")
        resolved = cache.resolve(org_name) if org_name else None
        customer_id = resolved[0] if resolved else "unassigned"
        customer_name = resolved[1] if resolved else org_name

        item = {
            "incident_id": str(incident.get("id", "")),
            "customer_id": customer_id,
            "customer_name": customer_name,
            "summary": incident.get("summary", ""),
            "severity": incident.get("severity", ""),
            "status": incident.get("status", ""),
            "type": incident.get("type", ""),
            "remediation": incident.get("remediation", ""),
            "created_at": incident.get("created_at", ""),
            "last_synced_at": synced_at,
        }
        incident_items.append(item)

    if incident_items:
        _batch_write(tbl_incidents, incident_items)

    totals = {
        "agents_upserted": len(agent_items),
        "incidents_upserted": len(incident_items),
    }
    logger.info("Huntress sync complete. Upserted: %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

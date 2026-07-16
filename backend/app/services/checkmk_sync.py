"""
AWS Lambda — CheckMK Monitoring Sync
=====================================
Fetches host and service monitoring data from the CheckMK REST API and writes
to DynamoDB tables CheckMKHosts and CheckMKServices.

Invoke schedule (recommended): EventBridge rule every 5–15 minutes.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:PutItem          (CheckMKHosts, CheckMKServices)
    dynamodb:BatchWriteItem   (CheckMKHosts, CheckMKServices)
    dynamodb:Scan             (CheckMKHosts, CheckMKServices)
    dynamodb:DeleteItem       (CheckMKHosts, CheckMKServices)

Environment variables
---------------------
    CHECKMK_BASE_URL      Base URL of the CheckMK instance (default: http://xg.checkmk.haley365.com)
    CHECKMK_SITE          CheckMK site name (default: XG)
    CHECKMK_USERNAME      CheckMK API username
    CHECKMK_PASSWORD      CheckMK API password (never hardcoded)
    CHECKMK_CUSTOMER_ID   Customer ID to tag all synced records with (default: FPC)
    DYNAMODB_REGION       AWS region where DynamoDB tables live (default: us-east-1)
    DYNAMODB_ENDPOINT_URL Override endpoint for local testing (e.g. DynamoDB Local)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import boto3
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHECKMK_BASE_URL: str = os.environ.get("CHECKMK_BASE_URL", "http://xg.checkmk.haley365.com")
CHECKMK_SITE: str = os.environ.get("CHECKMK_SITE", "XG")
CHECKMK_USERNAME: str = os.environ.get("CHECKMK_USERNAME", "")
CHECKMK_PASSWORD: str = os.environ.get("CHECKMK_PASSWORD", "")

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

TABLE_HOSTS = "CheckMKHosts"
TABLE_SERVICES = "CheckMKServices"
TABLE_CUSTOMERS = "Customers"

_BATCH_SIZE = 25

# CheckMK host state int → human-readable status
_HOST_STATE_MAP: dict[int, str] = {
    0: "Up",
    1: "Down",
    2: "Unreachable",
    -1: "Pending",
}

# CheckMK service state int → human-readable status
_SERVICE_STATE_MAP: dict[int, str] = {
    0: "Ok",
    1: "Warn",
    2: "Crit",
    3: "Unknown",
}


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
        reqs = [{"PutRequest": {"Item": item}} for item in chunk]
        response = table.meta.client.batch_write_item(
            RequestItems={table.name: reqs}
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _batch_delete(table: Any, pk_name: str, stale_ids: list[str]) -> None:
    """Delete records from DynamoDB whose primary key is in stale_ids."""
    for i in range(0, len(stale_ids), _BATCH_SIZE):
        chunk = stale_ids[i : i + _BATCH_SIZE]
        reqs = [{"DeleteRequest": {"Key": {pk_name: pk}}} for pk in chunk]
        response = table.meta.client.batch_write_item(
            RequestItems={table.name: reqs}
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _scan_existing_ids(table: Any, pk_name: str) -> set[str]:
    """Return the set of all primary key values currently in the table."""
    ids: set[str] = set()
    kwargs: dict[str, Any] = {"ProjectionExpression": pk_name}
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            ids.add(item[pk_name])
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return ids


def _resolve_customer(customers_table: Any, group: str, cache: dict) -> str:
    """Resolve a CheckMK host group name to a customer_id via the Customers table."""
    if group in cache:
        return cache[group]
    if not group:
        cache[group] = "unassigned"
        return "unassigned"
    try:
        from botocore.exceptions import ClientError as _ClientError
        resp = customers_table.get_item(Key={"customer_id": group})
        item = resp.get("Item")
        if item:
            cid = item.get("resolves_to") or group
            cache[group] = cid
            return cid
    except Exception:
        pass
    cache[group] = "unassigned"
    return "unassigned"


def _customer_for_host(groups: list, customers_table: Any, cache: dict) -> str:
    """Return the first group that resolves to a known customer, else 'unassigned'."""
    for g in groups:
        cid = _resolve_customer(customers_table, g, cache)
        if cid != "unassigned":
            return cid
    return "unassigned"


def _checkmk_session() -> requests.Session:
    """Return a requests Session pre-configured with CheckMK Bearer auth."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {CHECKMK_USERNAME} {CHECKMK_PASSWORD}",
            "Accept": "application/json",
        }
    )
    return session


def _api_url(path: str) -> str:
    return f"{CHECKMK_BASE_URL}/{CHECKMK_SITE}/check_mk/api/1.0{path}"


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------


def _fetch_hosts(session: requests.Session) -> list[dict]:
    """Fetch all hosts from CheckMK and return a list of raw extension dicts."""
    url = _api_url("/domain-types/host/collections/all")
    params = [
        ("columns", "name"),
        ("columns", "alias"),
        ("columns", "state"),
        ("columns", "address"),
        ("columns", "groups"),
    ]
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("CheckMK hosts API error: %s", exc)
        return []

    data = resp.json()
    return data.get("value", [])


def _fetch_problem_services(session: requests.Session) -> list[dict]:
    """Fetch all non-OK services from CheckMK."""
    url = _api_url("/domain-types/service/collections/all")
    # Filter to non-OK services (state != 0)
    query_filter = json.dumps({"op": "!=", "left": "state", "right": "0"})
    params = [
        ("query", query_filter),
        ("columns", "host_name"),
        ("columns", "description"),
        ("columns", "state"),
        ("columns", "plugin_output"),
    ]
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("CheckMK services API error: %s", exc)
        return []

    data = resp.json()
    return data.get("value", [])


def _fetch_all_services(session: requests.Session) -> list[dict]:
    """Fetch ALL services (for complete sync including OK ones)."""
    url = _api_url("/domain-types/service/collections/all")
    params = [
        ("columns", "host_name"),
        ("columns", "description"),
        ("columns", "state"),
        ("columns", "plugin_output"),
    ]
    try:
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("CheckMK all-services API error: %s", exc)
        return []

    data = resp.json()
    return data.get("value", [])


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    """Entry point invoked by EventBridge or a manual test event."""
    synced_at = _utcnow_iso()
    logger.info("Starting CheckMK sync at %s", synced_at)

    if not CHECKMK_USERNAME or not CHECKMK_PASSWORD:
        logger.error("CHECKMK_USERNAME and CHECKMK_PASSWORD must be set")
        return {"statusCode": 500, "body": json.dumps({"error": "Missing credentials"})}

    dynamo = _dynamo_resource()
    tbl_hosts = dynamo.Table(TABLE_HOSTS)
    tbl_services = dynamo.Table(TABLE_SERVICES)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    session = _checkmk_session()
    customer_cache: dict = {}

    # ── Hosts ─────────────────────────────────────────────────────────────────

    existing_host_ids = _scan_existing_ids(tbl_hosts, "host_name")
    raw_hosts = _fetch_hosts(session)
    logger.info("Fetched %d hosts from CheckMK", len(raw_hosts))

    host_items: list[dict] = []
    seen_host_ids: set[str] = set()
    # Build host_name → customer_id map for service tagging
    host_customer_map: dict[str, str] = {}

    for entry in raw_hosts:
        ext = entry.get("extensions", {})
        host_name: str = ext.get("name") or entry.get("id", "")
        if not host_name:
            continue

        state_int = ext.get("state", -1)
        if state_int is None:
            state_int = -1
        status = _HOST_STATE_MAP.get(int(state_int), "Pending")

        groups = ext.get("groups") or []
        if isinstance(groups, str):
            groups = [groups]

        customer_id = _customer_for_host(groups, tbl_customers, customer_cache)
        host_customer_map[host_name] = customer_id

        item: dict[str, Any] = {
            "host_name": host_name,
            "customer_id": customer_id,
            "alias": ext.get("alias", ""),
            "ip_address": ext.get("address", ""),
            "status": status,
            "state_int": state_int,
            "groups": groups,
            "last_synced_at": synced_at,
        }
        host_items.append(item)
        seen_host_ids.add(host_name)

    if host_items:
        _batch_write(tbl_hosts, host_items)
    logger.info("Upserted %d host records", len(host_items))

    # Delete stale hosts
    stale_hosts = list(existing_host_ids - seen_host_ids)
    if stale_hosts:
        _batch_delete(tbl_hosts, "host_name", stale_hosts)
        logger.info("Deleted %d stale host records", len(stale_hosts))

    # ── Services ──────────────────────────────────────────────────────────────

    existing_service_ids = _scan_existing_ids(tbl_services, "service_key")
    raw_services = _fetch_all_services(session)
    logger.info("Fetched %d services from CheckMK", len(raw_services))

    service_items: list[dict] = []
    seen_service_ids: set[str] = set()

    for entry in raw_services:
        ext = entry.get("extensions", {})
        host_name = ext.get("host_name", "")
        service_description = ext.get("description", "")
        if not host_name or not service_description:
            continue

        service_key = f"{host_name}|{service_description}"
        state_int = ext.get("state", 3)
        if state_int is None:
            state_int = 3
        status = _SERVICE_STATE_MAP.get(int(state_int), "Unknown")

        item = {
            "service_key": service_key,
            "customer_id": host_customer_map.get(host_name, "unassigned"),
            "host_name": host_name,
            "service_description": service_description,
            "status": status,
            "state_int": state_int,
            "plugin_output": ext.get("plugin_output", ""),
            "last_synced_at": synced_at,
        }
        service_items.append(item)
        seen_service_ids.add(service_key)

    if service_items:
        _batch_write(tbl_services, service_items)
    logger.info("Upserted %d service records", len(service_items))

    # Delete stale services
    stale_services = list(existing_service_ids - seen_service_ids)
    if stale_services:
        _batch_delete(tbl_services, "service_key", stale_services)
        logger.info("Deleted %d stale service records", len(stale_services))

    totals = {
        "hosts_upserted": len(host_items),
        "hosts_deleted": len(stale_hosts),
        "services_upserted": len(service_items),
        "services_deleted": len(stale_services),
    }
    logger.info("CheckMK sync complete. Totals: %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

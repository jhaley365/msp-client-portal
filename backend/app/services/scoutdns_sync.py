"""
AWS Lambda — ScoutDNS Sync
===========================
Fetches DNS stats, sites, networks, and roaming clients from the ScoutDNS API
for each mapped customer organization, then upserts the data into DynamoDB.

Invoke schedule (recommended): EventBridge rule every 6–24 hours.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:Scan             (Customers)
    dynamodb:PutItem          (ScoutDNSSummary, ScoutDNSSites, ScoutDNSClients)
    dynamodb:BatchWriteItem   (ScoutDNSSites, ScoutDNSClients)

Environment variables
---------------------
    SCOUTDNS_API_KEY       ScoutDNS API key (X-API-ACCESS-KEY header)
    DYNAMODB_REGION        AWS region where DynamoDB tables live (default: us-east-1)
    DYNAMODB_ENDPOINT_URL  Override endpoint for local testing
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOUTDNS_API_KEY: str = os.environ.get("SCOUTDNS_API_KEY", "")
SCOUTDNS_BASE_URL = "https://api.scoutdns.com/app"

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

TABLE_SUMMARY = "ScoutDNSSummary"
TABLE_SITES = "ScoutDNSSites"
TABLE_CLIENTS = "ScoutDNSClients"
TABLE_CUSTOMERS = "Customers"

_BATCH_SIZE = 25
_PERIOD = "Last 30 Days"


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


def _to_decimal(value: Any) -> Decimal:
    """Convert a numeric value to Decimal for DynamoDB storage."""
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


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


def _session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({
        "X-API-ACCESS-KEY": SCOUTDNS_API_KEY,
        "Accept": "application/json",
    })
    return sess


def _get(sess: requests.Session, path: str, params: dict | None = None) -> dict | list:
    url = f"{SCOUTDNS_BASE_URL}{path}"
    try:
        resp = sess.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("ScoutDNS API error %s: %s", path, exc)
        return {}


# ---------------------------------------------------------------------------
# Customer org cache (keyed by scoutdns_org_id)
# ---------------------------------------------------------------------------


def _load_customer_map(customers_table: Any) -> dict[str, list[tuple[str, str, str]]]:
    """Return {scoutdns_org_id: [(customer_id, customer_name, profile_filter), ...]}

    profile_filter is the ScoutDNS profile name that identifies this customer's
    roaming clients (e.g. "FPC-Users", "Staff"). Empty string means no filtering
    — all clients for the org are included.
    """
    org_map: dict[str, list[tuple[str, str, str]]] = {}
    kwargs: dict[str, Any] = {}
    while True:
        resp = customers_table.scan(**kwargs)
        for item in resp.get("Items", []):
            org_id: str = item.get("scoutdns_org_id", "")
            cid: str = item.get("customer_id", "")
            name: str = item.get("name", "")
            profile: str = item.get("scoutdns_profile", "")
            if org_id and cid:
                org_map.setdefault(org_id, []).append((cid, name, profile))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    total = sum(len(v) for v in org_map.values())
    logger.info("Loaded %d ScoutDNS customer mappings across %d orgs", total, len(org_map))
    return org_map


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    synced_at = _utcnow_iso()
    logger.info("Starting ScoutDNS sync at %s", synced_at)

    dynamo = _dynamo_resource()
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)
    tbl_summary = dynamo.Table(TABLE_SUMMARY)
    tbl_sites = dynamo.Table(TABLE_SITES)
    tbl_clients = dynamo.Table(TABLE_CLIENTS)

    customer_map = _load_customer_map(tbl_customers)
    if not customer_map:
        logger.warning("No customers have scoutdns_org_id set — nothing to sync.")
        return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": {}})}

    sess = _session()

    # Fetch all organizations to build org_id → org_name map
    orgs_resp = _get(sess, "/getOrganizations")
    orgs: list[dict] = orgs_resp.get("data", []) if isinstance(orgs_resp, dict) else []
    logger.info("Fetched %d ScoutDNS organizations", len(orgs))

    summaries_written = 0
    sites_written = 0
    clients_written = 0

    for org in orgs:
        org_id: str = str(org.get("id", ""))
        org_name: str = org.get("name", "")

        if org_id not in customer_map:
            logger.debug("No mapping for org %s (%s) — skipping", org_id, org_name)
            continue

        customers_for_org = customer_map[org_id]
        logger.info("Syncing org %s (%s) → %d customer(s)", org_name, org_id, len(customers_for_org))

        # ── Request stats by decision ──────────────────────────────────────────
        stats_resp = _get(sess, "/getRequestStatsByDecisions",
                          params={"period": _PERIOD, "organizationId": org_id})
        stats_data: dict = stats_resp.get("data", {}) if isinstance(stats_resp, dict) else {}
        allowed_requests = _to_decimal(stats_data.get("ALLOWED", 0))
        blocked_requests = _to_decimal(
            stats_data.get("FORBIDDEN", 0)
            + stats_data.get("BLOCKED", 0)
            + stats_data.get("DROP", 0)
        )

        # ── Threat stats ──────────────────────────────────────────────────────
        threats_resp = _get(sess, "/getThreatStats",
                            params={"period": _PERIOD, "organizationId": org_id})
        threats_data: list = threats_resp.get("data", []) if isinstance(threats_resp, dict) else []
        threat_count = _to_decimal(sum(t.get("count", 0) for t in threats_data))

        # ── Top blocked categories ─────────────────────────────────────────────
        cats_resp = _get(sess, "/getTopCategories",
                         params={"period": _PERIOD, "decision": "FORBIDDEN",
                                 "organizationId": org_id, "limit": 10})
        cats_data: dict = cats_resp.get("data", {}) if isinstance(cats_resp, dict) else {}
        top_categories = json.dumps([
            {"name": k, "count": v} for k, v in sorted(cats_data.items(), key=lambda x: -x[1])
        ])

        # ── Top blocked domains ───────────────────────────────────────────────
        domains_resp = _get(sess, "/getTopDomains",
                            params={"period": _PERIOD, "decision": "FORBIDDEN",
                                    "organizationId": org_id, "limit": 10})
        domains_data: dict = domains_resp.get("data", {}) if isinstance(domains_resp, dict) else {}
        top_domains = json.dumps([
            {"domain": k, "count": v} for k, v in sorted(domains_data.items(), key=lambda x: -x[1])
        ])

        # ── Roaming client counts ─────────────────────────────────────────────
        counts_resp = _get(sess, "/getClientCountStats", params={"organizationId": org_id})
        counts_data: dict = counts_resp.get("data", {}) if isinstance(counts_resp, dict) else {}
        online_clients = _to_decimal(counts_data.get("online", 0))
        offline_clients = _to_decimal(counts_data.get("offline", 0))

        # ── Sites (locations) ─────────────────────────────────────────────────
        sites_resp = _get(sess, "/getLocations", params={"organizationId": org_id})
        sites: list[dict] = sites_resp.get("data", []) if isinstance(sites_resp, dict) else []

        # ── Roaming clients ───────────────────────────────────────────────────
        clients_resp = _get(sess, "/getClients",
                            params={"organizationId": org_id, "limit": 500})
        clients: list[dict] = clients_resp.get("data", []) if isinstance(clients_resp, dict) else []

        # ── Write a record for every mapped customer ──────────────────────────
        for customer_id, customer_name, profile_filter in customers_for_org:
            tbl_summary.put_item(Item={
                "customer_id": customer_id,
                "customer_name": customer_name,
                "allowed_requests": allowed_requests,
                "blocked_requests": blocked_requests,
                "threat_count": threat_count,
                "top_categories": top_categories,
                "top_domains": top_domains,
                "online_clients": online_clients,
                "offline_clients": offline_clients,
                "period": _PERIOD,
                "last_synced_at": synced_at,
            })
            summaries_written += 1

            site_items: list[dict] = []
            for site in sites:
                sid = str(site.get("id", ""))
                if not sid:
                    continue
                site_items.append({
                    "site_id": f"{sid}#{customer_id}",
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "name": site.get("name", "") or "unknown",
                    "address": site.get("address", "") or "",
                    "last_synced_at": synced_at,
                })
            if site_items:
                _batch_write(tbl_sites, site_items)
                sites_written += len(site_items)

            filtered_clients = [
                c for c in clients
                if not profile_filter or (c.get("profile", "") or "").lower() == profile_filter.lower()
            ]
            client_items: list[dict] = []
            for client in filtered_clients:
                cid_val = str(client.get("id", ""))
                if not cid_val:
                    continue
                last_sync = client.get("lastSyncAt")
                last_sync_iso = (
                    datetime.fromtimestamp(last_sync / 1000, tz=timezone.utc).isoformat()
                    if last_sync else ""
                )
                client_items.append({
                    "client_id": f"{cid_val}#{customer_id}",
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "client_name": client.get("clientName", "") or "unknown",
                    "os_name": client.get("osName", "") or "",
                    "agent_status": (client.get("agentStatus", "") or "unknown").lower(),
                    "profile": client.get("profile", "") or "",
                    "version": client.get("version", "") or "",
                    "site": client.get("site", "") or "",
                    "policy": client.get("policy", "") or "",
                    "last_sync_at": last_sync_iso,
                    "last_synced_at": synced_at,
                })
            if client_items:
                _batch_write(tbl_clients, client_items)
                clients_written += len(client_items)

    totals = {
        "summaries_written": summaries_written,
        "sites_written": sites_written,
        "clients_written": clients_written,
    }
    logger.info("ScoutDNS sync complete. %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

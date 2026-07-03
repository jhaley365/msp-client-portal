"""
AWS Lambda — Office 365 Sync (multi-tenant)
============================================
Scans the Customers DynamoDB table for records that have o365_tenant_id,
o365_client_id, and o365_client_secret set, then fetches license SKUs and
users from Microsoft Graph for each tenant and upserts the data into the
O365Licenses and O365Mailboxes tables.

Invoke schedule (recommended): EventBridge rule every 60 minutes.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:Scan             (Customers)
    dynamodb:PutItem          (O365Licenses, O365Mailboxes)
    dynamodb:BatchWriteItem   (O365Licenses, O365Mailboxes)

Microsoft Graph API permissions required per app registration
-------------------------------------------------------------
    Organization.Read.All    (for /subscribedSkus)
    User.Read.All            (for /users)

Environment variables
---------------------
    DYNAMODB_REGION        AWS region where DynamoDB tables live (default: us-east-1)
    DYNAMODB_ENDPOINT_URL  Override endpoint for local testing
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

TABLE_CUSTOMERS = "Customers"
TABLE_LICENSES = "O365Licenses"
TABLE_MAILBOXES = "O365Mailboxes"

_BATCH_SIZE = 25
_USERS_PAGE_SIZE = 999


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
    for i in range(0, len(items), _BATCH_SIZE):
        chunk = items[i : i + _BATCH_SIZE]
        requests_list = [{"PutRequest": {"Item": item}} for item in chunk]
        response = table.meta.client.batch_write_item(
            RequestItems={table.name: requests_list}
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


# ---------------------------------------------------------------------------
# Customer credential scan
# ---------------------------------------------------------------------------


def _load_o365_customers(customers_table: Any) -> list[dict]:
    """Return all customers that have O365 credentials configured."""
    results: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = customers_table.scan(**kwargs)
        for item in resp.get("Items", []):
            if item.get("o365_tenant_id") and item.get("o365_client_id") and item.get("o365_client_secret"):
                results.append(item)
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    logger.info("Found %d customers with O365 credentials", len(results))
    return results


# ---------------------------------------------------------------------------
# Microsoft Graph auth
# ---------------------------------------------------------------------------


def _get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    url = TOKEN_URL_TEMPLATE.format(tenant_id=tenant_id)
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _graph_session(token: str) -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    return sess


# ---------------------------------------------------------------------------
# Graph API collectors
# ---------------------------------------------------------------------------


def _fetch_subscribed_skus(session: requests.Session) -> list[dict]:
    try:
        resp = session.get(f"{GRAPH_BASE_URL}/subscribedSkus", timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])
    except requests.RequestException as exc:
        logger.error("Graph error fetching /subscribedSkus: %s", exc)
        return []


def _fetch_users(session: requests.Session) -> list[dict]:
    url = f"{GRAPH_BASE_URL}/users"
    params = {
        "$select": "id,displayName,userPrincipalName,accountEnabled,assignedLicenses",
        "$top": str(_USERS_PAGE_SIZE),
    }
    users: list[dict] = []
    while url:
        try:
            resp = session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("Graph error fetching /users: %s", exc)
            break
        users.extend(data.get("value", []))
        url = data.get("@odata.nextLink", "")
        params = {}
    return users


def _fetch_mailbox_usage(session: requests.Session) -> dict[str, int]:
    """Fetch mailbox storage usage in MB keyed by UPN.

    Requires Reports.Read.All application permission on the app registration.
    Returns an empty dict silently if the permission is not granted.
    """
    import csv
    import io

    url = f"{GRAPH_BASE_URL}/reports/getMailboxUsageDetail(period='D7')"
    try:
        # Graph returns CSV for report endpoints
        resp = session.get(url, headers={"Accept": "text/csv"}, timeout=60)
        if resp.status_code == 403:
            logger.warning("Reports.Read.All not granted — mailbox sizes will be 0")
            return {}
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        usage: dict[str, int] = {}
        for row in reader:
            upn = row.get("User Principal Name", "").strip()
            bytes_used = row.get("Storage Used (Byte)", "0").strip() or "0"
            if upn:
                usage[upn.lower()] = int(int(bytes_used) / (1024 * 1024))  # bytes → MB
        return usage
    except requests.RequestException as exc:
        logger.warning("Could not fetch mailbox usage report: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    synced_at = _utcnow_iso()
    logger.info("Starting O365 multi-tenant sync at %s", synced_at)

    dynamo = _dynamo_resource()
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)
    tbl_licenses = dynamo.Table(TABLE_LICENSES)
    tbl_mailboxes = dynamo.Table(TABLE_MAILBOXES)

    customers = _load_o365_customers(tbl_customers)
    if not customers:
        logger.warning("No customers have O365 credentials set — nothing to sync.")
        return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": {}})}

    total_licenses = 0
    total_mailboxes = 0

    for customer in customers:
        customer_id: str = customer["customer_id"]
        customer_name: str = customer.get("name", "")
        tenant_id: str = customer["o365_tenant_id"]
        client_id: str = customer["o365_client_id"]
        client_secret: str = customer["o365_client_secret"]

        logger.info("Syncing O365 tenant for customer %s (%s)", customer_name, customer_id)

        try:
            token = _get_access_token(tenant_id, client_id, client_secret)
        except requests.HTTPError as exc:
            logger.error("Failed to get token for customer %s: %s", customer_id, exc)
            continue

        session = _graph_session(token)

        # ── License SKUs ──────────────────────────────────────────────────────
        raw_skus = _fetch_subscribed_skus(session)
        logger.info("Customer %s: fetched %d SKU(s)", customer_id, len(raw_skus))

        # Build skuId → skuPartNumber map for resolving user license names
        sku_id_to_name: dict[str, str] = {
            sku.get("skuId", ""): sku.get("skuPartNumber", "")
            for sku in raw_skus if sku.get("skuId")
        }

        license_items: list[dict] = []
        for sku in raw_skus:
            sku_id: str = sku.get("skuId", "")
            sku_name: str = sku.get("skuPartNumber", "")
            consumed_units: int = int(sku.get("consumedUnits", 0))
            prepaid = sku.get("prepaidUnits", {})
            total_units: int = int(prepaid.get("enabled", 0))
            available_units: int = max(0, total_units - consumed_units)

            license_items.append({
                "license_id": f"{customer_id}#{sku_id}",
                "customer_id": customer_id,
                "customer_name": customer_name,
                "sku_name": sku_name,
                "total_units": total_units,
                "consumed_units": consumed_units,
                "available_units": available_units,
                "last_synced_at": synced_at,
            })

        if license_items:
            _batch_write(tbl_licenses, license_items)
            total_licenses += len(license_items)

        # ── Mailbox usage report ──────────────────────────────────────────────
        mailbox_usage = _fetch_mailbox_usage(session)

        # ── Users / Mailboxes ─────────────────────────────────────────────────
        raw_users = _fetch_users(session)
        logger.info("Customer %s: fetched %d user(s)", customer_id, len(raw_users))

        mailbox_items: list[dict] = []
        for user in raw_users:
            upn: str = user.get("userPrincipalName", "")
            if not upn or upn.lower().startswith("sync_"):
                continue
            assigned = user.get("assignedLicenses", [])
            license_names = [
                sku_id_to_name.get(lic.get("skuId", ""), "")
                for lic in assigned
                if sku_id_to_name.get(lic.get("skuId", ""), "")
            ]
            mailbox_size_mb = mailbox_usage.get(upn.lower(), 0)
            mailbox_items.append({
                "mailbox_id": f"{customer_id}#{upn}",
                "customer_id": customer_id,
                "customer_name": customer_name,
                "display_name": user.get("displayName", "") or "",
                "email": upn,
                "account_enabled": user.get("accountEnabled", True),
                "licensed": len(assigned) > 0,
                "license_names": ", ".join(license_names) if license_names else "",
                "mailbox_size_mb": mailbox_size_mb,
                "last_synced_at": synced_at,
            })

        if mailbox_items:
            _batch_write(tbl_mailboxes, mailbox_items)
            total_mailboxes += len(mailbox_items)

    totals = {
        "licenses_upserted": total_licenses,
        "mailboxes_upserted": total_mailboxes,
    }
    logger.info("O365 sync complete. %s", totals)
    return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": totals})}

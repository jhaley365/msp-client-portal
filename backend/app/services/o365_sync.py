"""
AWS Lambda — Office 365 Sync
==============================
Fetches license SKUs and mailbox information from the Microsoft Graph API
and upserts the data into the O365Licenses and O365Mailboxes DynamoDB tables.

Since an O365 tenant is typically tied to a single MSP customer, the
``O365_CUSTOMER_ID`` environment variable identifies which Customers record
these licenses and mailboxes belong to.

Invoke schedule (recommended): EventBridge rule every 60 minutes.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:PutItem          (O365Licenses, O365Mailboxes)
    dynamodb:BatchWriteItem   (O365Licenses, O365Mailboxes)

Microsoft Graph API permissions required (application permissions)
------------------------------------------------------------------
    Organization.Read.All    (for /subscribedSkus)
    User.Read.All            (for /users)
    MailboxSettings.Read     (for /users/{id}/mailboxSettings)

Environment variables
---------------------
    O365_TENANT_ID       Azure AD tenant ID (GUID)
    O365_CLIENT_ID       Azure AD application (client) ID
    O365_CLIENT_SECRET   Azure AD client secret value
    O365_CUSTOMER_ID     Portal customer_id that owns this O365 tenant
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

O365_TENANT_ID: str = os.environ.get("O365_TENANT_ID", "")
O365_CLIENT_ID: str = os.environ.get("O365_CLIENT_ID", "")
O365_CLIENT_SECRET: str = os.environ.get("O365_CLIENT_SECRET", "")
O365_CUSTOMER_ID: str = os.environ.get("O365_CUSTOMER_ID", "unassigned")

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)

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


# ---------------------------------------------------------------------------
# Microsoft Graph authentication
# ---------------------------------------------------------------------------


def _get_access_token() -> str:
    """Obtain an OAuth2 bearer token via the client credentials flow.

    Returns
    -------
    str
        The access token string.

    Raises
    ------
    requests.HTTPError
        If the token request fails.
    """
    url = TOKEN_URL_TEMPLATE.format(tenant_id=O365_TENANT_ID)
    data = {
        "grant_type": "client_credentials",
        "client_id": O365_CLIENT_ID,
        "client_secret": O365_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    token: str = resp.json()["access_token"]
    logger.info("Successfully obtained Microsoft Graph access token")
    return token


def _graph_session(token: str) -> requests.Session:
    """Return a requests Session pre-configured with the Graph bearer token."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
    )
    return session


# ---------------------------------------------------------------------------
# Graph API data collectors
# ---------------------------------------------------------------------------


def _fetch_subscribed_skus(session: requests.Session) -> list[dict]:
    """Fetch all subscribed license SKUs from /subscribedSkus.

    Returns
    -------
    list[dict]
        Raw SKU objects from the Graph API.
    """
    url = f"{GRAPH_BASE_URL}/subscribedSkus"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])
    except requests.RequestException as exc:
        logger.error("Graph API error fetching /subscribedSkus: %s", exc)
        return []


def _fetch_users(session: requests.Session) -> list[dict]:
    """Paginate through /users, collecting all user records.

    Uses ``@odata.nextLink`` for pagination as directed by the Graph API.

    Returns
    -------
    list[dict]
        All user objects from the Graph API.
    """
    url = f"{GRAPH_BASE_URL}/users"
    params = {
        "$select": "id,displayName,userPrincipalName,mailboxSettings",
        "$top": str(_USERS_PAGE_SIZE),
    }
    users: list[dict] = []

    while url:
        try:
            resp = session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("Graph API error fetching /users: %s", exc)
            break

        users.extend(data.get("value", []))
        logger.debug("Fetched %d users so far", len(users))

        # Follow the next page link; clear params so they are not re-sent.
        url = data.get("@odata.nextLink", "")
        params = {}

    return users


def _fetch_mailbox_settings(session: requests.Session, user_id: str) -> dict:
    """Fetch mailbox settings for a single user.

    Note: True mailbox size statistics (used_size_mb, item_count) require
    the Exchange Online REST API or the Microsoft Graph mailboxUsage report
    endpoint rather than mailboxSettings.  Those fields are set to 0 here.

    # TODO: Integrate Exchange mailbox stats when Exchange permissions are available.
    """
    url = f"{GRAPH_BASE_URL}/users/{user_id}/mailboxSettings"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("Could not fetch mailboxSettings for user %s: %s", user_id, exc)
        return {}


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    """Entry point invoked by EventBridge or a manual test event."""
    synced_at = _utcnow_iso()
    logger.info(
        "Starting O365 sync at %s for customer_id=%s", synced_at, O365_CUSTOMER_ID
    )

    # Obtain Graph API access token.
    try:
        token = _get_access_token()
    except requests.HTTPError as exc:
        logger.error("Failed to obtain Microsoft Graph token: %s", exc)
        raise

    session = _graph_session(token)

    dynamo = _dynamo_resource()
    tbl_licenses = dynamo.Table(TABLE_LICENSES)
    tbl_mailboxes = dynamo.Table(TABLE_MAILBOXES)

    # ── License SKUs ──────────────────────────────────────────────────────────

    raw_skus = _fetch_subscribed_skus(session)
    logger.info("Fetched %d subscribed SKU(s)", len(raw_skus))

    license_items: list[dict] = []
    for sku in raw_skus:
        sku_id: str = sku.get("skuId", "")
        sku_name: str = sku.get("skuPartNumber", "")
        consumed_units: int = int(sku.get("consumedUnits", 0))
        prepaid = sku.get("prepaidUnits", {})
        total_units: int = int(prepaid.get("enabled", 0))
        available_units: int = max(0, total_units - consumed_units)

        license_id = f"{O365_CUSTOMER_ID}#{sku_id}"

        item: dict[str, Any] = {
            "license_id": license_id,
            "customer_id": O365_CUSTOMER_ID,
            "customer_name": "",  # Not stored per-O365-tenant; set if desired.
            "sku_name": sku_name,
            "total_units": total_units,
            "consumed_units": consumed_units,
            "available_units": available_units,
            "last_synced_at": synced_at,
        }
        license_items.append(item)

    if license_items:
        _batch_write(tbl_licenses, license_items)

    # ── Mailboxes ─────────────────────────────────────────────────────────────

    raw_users = _fetch_users(session)
    logger.info("Fetched %d user(s) from Graph", len(raw_users))

    mailbox_items: list[dict] = []
    for user in raw_users:
        upn: str = user.get("userPrincipalName", "")
        if not upn:
            continue

        # mailboxSettings embedded on the user object (from $select).
        mailbox_settings: dict = user.get("mailboxSettings") or {}

        # TODO: Fetch actual mailbox usage (total_size_mb, used_size_mb,
        # item_count) from the Exchange endpoint:
        #   GET /users/{id}/drive/root (OneDrive) or
        #   GET /reports/getMailboxUsageDetail — requires Reports.Read.All
        # Until then, set to 0 as placeholder values.
        item = {
            "mailbox_id": upn,
            "customer_id": O365_CUSTOMER_ID,
            "customer_name": "",  # Set if desired.
            "display_name": user.get("displayName", ""),
            "email": upn,
            "mailbox_type": mailbox_settings.get("userPurpose", "UserMailbox"),
            "total_size_mb": 0,   # TODO: populate from Exchange/Reports API
            "used_size_mb": 0,    # TODO: populate from Exchange/Reports API
            "item_count": 0,      # TODO: populate from Exchange/Reports API
            "last_synced_at": synced_at,
        }
        mailbox_items.append(item)

    if mailbox_items:
        _batch_write(tbl_mailboxes, mailbox_items)

    totals = {
        "licenses_upserted": len(license_items),
        "mailboxes_upserted": len(mailbox_items),
    }
    logger.info("O365 sync complete. Upserted: %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

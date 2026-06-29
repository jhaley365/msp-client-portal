"""
AWS Lambda — Syncro Ticket Sync
================================
Fetches all tickets from the Syncro MSP API for every customer in the
Customers DynamoDB table and upserts them into the SyncroTickets table.

Each customer record must contain a ``syncro_customer_id`` field that maps
to the corresponding customer ID in Syncro.  Customers without this field
are skipped.

Invoke schedule (recommended): EventBridge rule every 15–60 minutes.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    dynamodb:Scan             (Customers)
    dynamodb:PutItem          (SyncroTickets)
    dynamodb:BatchWriteItem   (SyncroTickets)

Environment variables
---------------------
    SYNCRO_API_KEY       API key for the Syncro MSP API
    SYNCRO_SUBDOMAIN     Syncro subdomain (e.g. "acme" for acme.syncromsp.com)
    DYNAMODB_REGION      AWS region where DynamoDB tables live (default: us-east-1)
    DYNAMODB_ENDPOINT_URL  Override endpoint for local testing (e.g. DynamoDB Local)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

# Only sync tickets created on or after this date (YYYY-MM-DD).
# Set to None to sync all historical tickets.
_SINCE_DATE: str | None = f"{datetime.now(tz=timezone.utc).year}-01-01"

import boto3
from botocore.exceptions import ClientError

from app.integrations.syncro import SyncroClient, SyncroAPIError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

TABLE_SYNCRO_TICKETS = "SyncroTickets"
TABLE_CUSTOMERS = "Customers"

# DynamoDB BatchWriteItem accepts at most 25 items per call.
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


def _batch_write(table: Any, items: list[dict]) -> None:
    """Write items in batches of 25, retrying unprocessed items once."""
    for i in range(0, len(items), _BATCH_SIZE):
        chunk = items[i : i + _BATCH_SIZE]
        requests = [{"PutRequest": {"Item": item}} for item in chunk]
        response = table.meta.client.batch_write_item(
            RequestItems={table.name: requests}
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            # Single retry for unprocessed items.
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _scan_all_customers(customers_table: Any) -> list[dict]:
    """Scan the Customers table and return all items."""
    items: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = customers_table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


# ---------------------------------------------------------------------------
# Async fetch logic
# ---------------------------------------------------------------------------


async def _fetch_all_tickets_for_customer(
    client: SyncroClient,
    syncro_customer_id: str | int,
) -> list[dict]:
    """Paginate through all Syncro ticket pages for a customer.

    Parameters
    ----------
    client:
        Authenticated SyncroClient instance.
    syncro_customer_id:
        The Syncro customer ID to query tickets for.

    Returns
    -------
    list[dict]
        Raw ticket data dicts from all pages.
    """
    all_tickets: list[dict] = []
    page = 1

    while True:
        try:
            ticket_list = await client.get_tickets(
                customer_id=syncro_customer_id, page=page, since_date=_SINCE_DATE
            )
        except SyncroAPIError as exc:
            logger.error(
                "Syncro API error fetching tickets for customer %s page %d: %s",
                syncro_customer_id,
                page,
                exc,
            )
            break

        all_tickets.extend([t.model_dump() for t in ticket_list.tickets])
        logger.debug(
            "Fetched page %d for Syncro customer %s (%d tickets so far)",
            page,
            syncro_customer_id,
            len(all_tickets),
        )

        total_pages = ticket_list.total_pages
        if total_pages is None or page >= total_pages:
            break
        page += 1

    return all_tickets


async def _sync_all(customers: list[dict], synced_at: str) -> list[dict]:
    """Fetch tickets for every customer that has a syncro_customer_id.

    Returns a flat list of DynamoDB items ready to be batch-written.
    """
    dynamo_items: list[dict] = []

    async with SyncroClient() as client:
        for customer in customers:
            syncro_customer_id = customer.get("syncro_customer_id")
            if not syncro_customer_id:
                logger.debug(
                    "Skipping customer %s — no syncro_customer_id field",
                    customer.get("customer_id"),
                )
                continue

            customer_id: str = customer["customer_id"]
            customer_name: str = customer.get("name", "")

            raw_tickets = await _fetch_all_tickets_for_customer(
                client, syncro_customer_id
            )
            logger.info(
                "Customer %s (%s): fetched %d Syncro tickets",
                customer_id,
                customer_name,
                len(raw_tickets),
            )

            for ticket in raw_tickets:
                item: dict[str, Any] = {
                    # Use string ticket_id as the DynamoDB PK.
                    "ticket_id": str(ticket.get("id", ticket.get("ticket_id", ""))),
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "subject": ticket.get("subject", ""),
                    "status": ticket.get("status", ""),
                    "priority": ticket.get("priority") or "",
                    "assigned_tech": ticket.get("assigned_tech")
                    or ticket.get("user_email")
                    or "",
                    "problem_type": ticket.get("problem_type") or "",
                    "created_at": ticket.get("created_at", ""),
                    "updated_at": ticket.get("updated_at", ""),
                    "last_synced_at": synced_at,
                }
                dynamo_items.append(item)

    return dynamo_items


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    """Entry point invoked by EventBridge or a manual test event."""
    synced_at = _utcnow_iso()
    logger.info("Starting Syncro ticket sync at %s", synced_at)

    dynamo = _dynamo_resource()
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)
    tbl_tickets = dynamo.Table(TABLE_SYNCRO_TICKETS)

    # Fetch all portal customers.
    try:
        customers = _scan_all_customers(tbl_customers)
    except ClientError as exc:
        logger.error("Failed to scan Customers table: %s", exc)
        raise

    logger.info("Found %d customer(s) to process", len(customers))

    # Fetch tickets from Syncro (async) and convert to DynamoDB items.
    dynamo_items = asyncio.run(_sync_all(customers, synced_at))

    # Batch-write all tickets to DynamoDB.
    if dynamo_items:
        _batch_write(tbl_tickets, dynamo_items)

    totals = {"tickets_upserted": len(dynamo_items)}
    logger.info("Syncro ticket sync complete. Upserted: %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

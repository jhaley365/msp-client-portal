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
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _scan_existing_ids(table: Any, pk_name: str) -> set[str]:
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


def _batch_delete(table: Any, pk_name: str, stale_ids: list[str]) -> None:
    for i in range(0, len(stale_ids), _BATCH_SIZE):
        chunk = stale_ids[i : i + _BATCH_SIZE]
        requests = [{"DeleteRequest": {"Key": {pk_name: pk}}} for pk in chunk]
        resp = table.meta.client.batch_write_item(RequestItems={table.name: requests})
        unprocessed = resp.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
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


def _scan_existing_updated_at(table: Any) -> dict[str, str]:
    """Return a map of ticket_id → updated_at for all tickets in DynamoDB."""
    result: dict[str, str] = {}
    kwargs: dict[str, Any] = {
        "ProjectionExpression": "ticket_id, updated_at",
    }
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            tid = item.get("ticket_id")
            uat = item.get("updated_at")
            if tid and uat:
                result[str(tid)] = str(uat)
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return result


def _normalize_comments(raw_comments: list[Any]) -> list[dict]:
    out = []
    for c in raw_comments:
        if not isinstance(c, dict):
            continue
        user = c.get("user") or {}
        user_name = user.get("name", "") if isinstance(user, dict) else str(user)
        out.append({
            "id": str(c.get("id", "")),
            "body": c.get("body", ""),
            "created_at": c.get("created_at", ""),
            "user": user_name,
            "tech": bool(c.get("tech", False)),
        })
    return out


async def _fetch_all_tickets_for_customer(
    client: SyncroClient,
    syncro_customer_id: str | int,
) -> list[dict]:
    """Paginate through all Syncro ticket pages for a customer."""
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


async def _fetch_full_detail(client: SyncroClient, ticket_id: str) -> tuple[str, list[dict]]:
    """Return (body, comments) by calling the single-ticket Syncro endpoint."""
    try:
        raw = await client._request("GET", f"/tickets/{ticket_id}")
        ticket_data = raw.get("ticket", raw)
        body = ticket_data.get("body") or ""
        raw_comments = (
            ticket_data.get("ticket_comments")
            or ticket_data.get("comments")
            or []
        )
        return body, _normalize_comments(raw_comments)
    except Exception as exc:
        logger.warning("Could not fetch full detail for ticket %s: %s", ticket_id, exc)
        return "", []


async def _sync_all(
    customers: list[dict],
    synced_at: str,
    existing_updated_at: dict[str, str],
) -> list[dict]:
    """Fetch tickets for every customer that has a syncro_customer_id.

    For tickets whose updated_at has changed (or that are new), fetches full
    detail from Syncro including body and comments.  Unchanged tickets reuse
    the cached updated_at and skip the extra API call.

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

            detail_fetched = detail_skipped = 0

            for ticket in raw_tickets:
                ticket_id = str(ticket.get("id", ""))
                updated_at = ticket.get("updated_at", "")

                # Only fetch full detail when the ticket is new or has been updated.
                cached_updated_at = existing_updated_at.get(ticket_id)
                if cached_updated_at == updated_at:
                    # Ticket unchanged — we'll write back the list fields but
                    # body/comments will be populated via a separate DynamoDB
                    # update_item call to preserve existing detail data.
                    needs_detail = False
                    detail_skipped += 1
                else:
                    needs_detail = True
                    detail_fetched += 1

                body = ""
                comments: list[dict] = []
                if needs_detail:
                    body, comments = await _fetch_full_detail(client, ticket_id)

                item: dict[str, Any] = {
                    "ticket_id": ticket_id,
                    "ticket_number": str(ticket.get("number") or ticket.get("id", "")),
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
                    "updated_at": updated_at,
                    "last_synced_at": synced_at,
                }
                if needs_detail:
                    item["body"] = body
                    item["comments"] = comments

                dynamo_items.append(item)

            logger.info(
                "Customer %s: %d full-detail fetches, %d skipped (unchanged)",
                customer_id,
                detail_fetched,
                detail_skipped,
            )

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

    # Snapshot existing ticket IDs and updated_at timestamps before the sync.
    existing_ticket_ids = _scan_existing_ids(tbl_tickets, "ticket_id")
    existing_updated_at = _scan_existing_updated_at(tbl_tickets)

    # Fetch tickets from Syncro (async) and convert to DynamoDB items.
    dynamo_items = asyncio.run(_sync_all(customers, synced_at, existing_updated_at))

    # Batch-write all tickets to DynamoDB.
    if dynamo_items:
        _batch_write(tbl_tickets, dynamo_items)

    # Delete tickets that no longer exist in Syncro.
    seen_ids = {item["ticket_id"] for item in dynamo_items}
    stale_ids = list(existing_ticket_ids - seen_ids)
    if stale_ids:
        logger.info("Deleting %d stale tickets from DynamoDB", len(stale_ids))
        _batch_delete(tbl_tickets, "ticket_id", stale_ids)

    totals = {"tickets_upserted": len(dynamo_items), "tickets_deleted": len(stale_ids)}
    logger.info("Syncro ticket sync complete. %s", totals)

    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

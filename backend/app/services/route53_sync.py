"""Route 53 hosted zone sync — global service, upserts into DynamoDB."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
TABLE_ZONES = "Route53Zones"
TABLE_CUSTOMERS = "Customers"
_BATCH_SIZE = 25
_TAG_CHUNK = 10  # Route 53 list_tags_for_resources max


def _dynamo_resource() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _batch_write(table: Any, items: list[dict]) -> None:
    for i in range(0, len(items), _BATCH_SIZE):
        chunk = items[i: i + _BATCH_SIZE]
        requests = [{"PutRequest": {"Item": item}} for item in chunk]
        resp = table.meta.client.batch_write_item(RequestItems={table.name: requests})
        unprocessed = resp.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _batch_delete(table: Any, pk_name: str, stale_ids: list[str]) -> None:
    for i in range(0, len(stale_ids), _BATCH_SIZE):
        chunk = stale_ids[i: i + _BATCH_SIZE]
        requests = [{"DeleteRequest": {"Key": {pk_name: pk}}} for pk in chunk]
        resp = table.meta.client.batch_write_item(RequestItems={table.name: requests})
        unprocessed = resp.get("UnprocessedItems", {}).get(table.name, [])
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


def _resolve_customer(customers_table: Any, client_tag: str, cache: dict) -> str:
    if client_tag in cache:
        return cache[client_tag]
    if not client_tag:
        cache[client_tag] = "unassigned"
        return "unassigned"
    try:
        resp = customers_table.get_item(Key={"customer_id": client_tag})
        item = resp.get("Item")
        if item:
            cid = item.get("resolves_to") or client_tag
            cache[client_tag] = cid
            return cid
    except ClientError:
        pass
    cache[client_tag] = "unassigned"
    return "unassigned"


def _fetch_zone_tags(r53: Any, zone_ids: list[str]) -> dict[str, dict[str, str]]:
    """Batch-fetch tags for up to _TAG_CHUNK zone IDs at a time."""
    result: dict[str, dict[str, str]] = {}
    for i in range(0, len(zone_ids), _TAG_CHUNK):
        chunk = zone_ids[i: i + _TAG_CHUNK]
        try:
            resp = r53.list_tags_for_resources(ResourceType="hostedzone", ResourceIds=chunk)
            for tag_set in resp.get("ResourceTagSets", []):
                rid = tag_set["ResourceId"]
                result[rid] = {t["Key"]: t["Value"] for t in tag_set.get("Tags", [])}
        except ClientError as exc:
            logger.warning("list_tags_for_resources failed: %s", exc)
    return result


def lambda_handler(event: dict, context: Any) -> dict:
    synced_at = _utcnow_iso()
    r53 = boto3.client("route53")
    dynamo = _dynamo_resource()
    tbl_zones = dynamo.Table(TABLE_ZONES)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    # List all hosted zones (paginated)
    zones: list[dict] = []
    kwargs: dict[str, Any] = {}
    while True:
        resp = r53.list_hosted_zones(**kwargs)
        zones.extend(resp.get("HostedZones", []))
        if resp.get("IsTruncated"):
            kwargs["Marker"] = resp["NextMarker"]
        else:
            break

    # Strip /hostedzone/ prefix from IDs
    zone_ids = [z["Id"].split("/")[-1] for z in zones]
    tags_by_id = _fetch_zone_tags(r53, zone_ids)

    # Count records per zone
    def _record_count(zone_id: str) -> int:
        try:
            resp = r53.get_hosted_zone(Id=zone_id)
            return int(resp.get("HostedZone", {}).get("ResourceRecordSetCount", 0))
        except ClientError:
            return 0

    existing_ids = _scan_existing_ids(tbl_zones, "zone_id")
    seen_ids: set[str] = set()
    cache: dict = {}
    items: list[dict] = []

    for zone in zones:
        raw_id = zone["Id"].split("/")[-1]
        tags = tags_by_id.get(raw_id, {})
        client_tag = tags.get("Client", "")
        customer_id = _resolve_customer(tbl_customers, client_tag, cache)
        config = zone.get("Config", {})
        items.append({
            "zone_id": raw_id,
            "customer_id": customer_id,
            "client_tag": client_tag,
            "name": zone.get("Name", "").rstrip("."),
            "private_zone": config.get("PrivateZone", False),
            "comment": config.get("Comment", ""),
            "record_count": zone.get("ResourceRecordSetCount", 0),
            "caller_reference": zone.get("CallerReference", ""),
            "last_synced_at": synced_at,
        })
        seen_ids.add(raw_id)

    if items:
        _batch_write(tbl_zones, items)

    stale = list(existing_ids - seen_ids)
    deleted = 0
    if stale:
        _batch_delete(tbl_zones, "zone_id", stale)
        deleted = len(stale)

    totals = {"zones": len(items), "deleted": deleted}
    logger.info("Route 53 sync complete: %s", totals)
    return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": totals})}

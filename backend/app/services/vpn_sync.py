"""Site-to-Site VPN sync — scans all regions, upserts into DynamoDB."""

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
TABLE_VPN = "VPNConnections"
TABLE_CUSTOMERS = "Customers"
_BATCH_SIZE = 25


def _dynamo_resource() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _tag_map(tags: list[dict] | None) -> dict[str, str]:
    if not tags:
        return {}
    return {t["Key"]: t["Value"] for t in tags}


def _get_regions() -> list[str]:
    env = os.environ.get("EC2_REGIONS", "").strip()
    if env:
        return [r.strip() for r in env.split(",") if r.strip()]
    ec2 = boto3.client("ec2", region_name="us-east-1")
    resp = ec2.describe_regions(
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}]
    )
    return [r["RegionName"] for r in resp["Regions"]]


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


def collect_vpn_connections(region: str, synced_at: str, customers_table: Any, cache: dict) -> list[dict]:
    ec2 = boto3.client("ec2", region_name=region)
    try:
        paginator = ec2.get_paginator("describe_vpn_connections")
        raw: list[dict] = []
        for page in paginator.paginate():
            raw.extend(page.get("VpnConnections", []))
    except ClientError as exc:
        logger.warning("describe_vpn_connections failed in %s: %s", region, exc)
        return []

    items: list[dict] = []
    for vpn in raw:
        tags = _tag_map(vpn.get("Tags"))
        client_tag = tags.get("Client", "")
        customer_id = _resolve_customer(customers_table, client_tag, cache)
        name = tags.get("Name", "")

        # Parse tunnel telemetry (up to 2 tunnels)
        tunnels = []
        for t in vpn.get("VgwTelemetry", []):
            last_change = t.get("LastStatusChange")
            tunnels.append({
                "outside_ip": t.get("OutsideIpAddress", ""),
                "status": t.get("Status", ""),
                "status_message": t.get("StatusMessage", ""),
                "last_status_change": last_change.isoformat() if last_change else "",
                "accepted_route_count": t.get("AcceptedRouteCount", 0),
            })

        options = vpn.get("Options") or {}
        items.append({
            "vpn_id": vpn["VpnConnectionId"],
            "customer_id": customer_id,
            "client_tag": client_tag,
            "name": name,
            "state": vpn.get("State", ""),
            "type": vpn.get("Type", ""),
            "category": vpn.get("Category", ""),
            "region": region,
            "vpn_gateway_id": vpn.get("VpnGatewayId", ""),
            "transit_gateway_id": vpn.get("TransitGatewayId", ""),
            "customer_gateway_id": vpn.get("CustomerGatewayId", ""),
            "customer_gateway_address": vpn.get("CustomerGatewayConfiguration", ""),
            "routing": options.get("StaticRoutesOnly", False) and "Static" or "Dynamic",
            "tunnel1_outside_ip": tunnels[0]["outside_ip"] if len(tunnels) > 0 else "",
            "tunnel1_status": tunnels[0]["status"] if len(tunnels) > 0 else "",
            "tunnel1_last_change": tunnels[0]["last_status_change"] if len(tunnels) > 0 else "",
            "tunnel2_outside_ip": tunnels[1]["outside_ip"] if len(tunnels) > 1 else "",
            "tunnel2_status": tunnels[1]["status"] if len(tunnels) > 1 else "",
            "tunnel2_last_change": tunnels[1]["last_status_change"] if len(tunnels) > 1 else "",
            "tunnels": tunnels,
            "last_synced_at": synced_at,
        })

    logger.info("Region %s: collected %d VPN connections", region, len(items))
    return items


def lambda_handler(event: dict, context: Any) -> dict:
    synced_at = _utcnow_iso()
    regions = _get_regions()
    dynamo = _dynamo_resource()
    tbl_vpn = dynamo.Table(TABLE_VPN)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    existing_ids = _scan_existing_ids(tbl_vpn, "vpn_id")
    seen_ids: set[str] = set()
    cache: dict = {}
    totals = {"vpn_connections": 0, "deleted": 0}

    for region in regions:
        try:
            items = collect_vpn_connections(region, synced_at, tbl_customers, cache)
            if items:
                _batch_write(tbl_vpn, items)
            totals["vpn_connections"] += len(items)
            seen_ids.update(i["vpn_id"] for i in items)
        except ClientError as exc:
            logger.error("Error processing region %s: %s", region, exc)

    stale = list(existing_ids - seen_ids)
    if stale:
        _batch_delete(tbl_vpn, "vpn_id", stale)
        totals["deleted"] = len(stale)

    logger.info("VPN sync complete: %s", totals)
    return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": totals})}

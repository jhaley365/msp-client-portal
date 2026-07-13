"""FSx file system sync — scans all regions, upserts into DynamoDB."""

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
TABLE_FSX = "FSxFileSystems"
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


def collect_fsx(region: str, synced_at: str, customers_table: Any, cache: dict) -> list[dict]:
    fsx = boto3.client("fsx", region_name=region)
    try:
        paginator = fsx.get_paginator("describe_file_systems")
        file_systems: list[dict] = []
        for page in paginator.paginate():
            file_systems.extend(page.get("FileSystems", []))
    except ClientError as exc:
        logger.warning("describe_file_systems failed in %s: %s", region, exc)
        return []

    items: list[dict] = []
    for fs in file_systems:
        tags = _tag_map(fs.get("Tags"))
        client_tag = tags.get("Client", "")
        customer_id = _resolve_customer(customers_table, client_tag, cache)
        fs_type = fs.get("FileSystemType", "")

        # Pull type-specific details
        storage_capacity = fs.get("StorageCapacity", 0)
        throughput_capacity = 0
        dns_name = fs.get("DNSName", "")

        if fs_type == "WINDOWS":
            win = fs.get("WindowsConfiguration") or {}
            throughput_capacity = win.get("ThroughputCapacity", 0)
        elif fs_type == "LUSTRE":
            lus = fs.get("LustreConfiguration") or {}
            throughput_capacity = lus.get("PerUnitStorageThroughput", 0)
        elif fs_type == "ONTAP":
            ont = fs.get("OntapConfiguration") or {}
            throughput_capacity = ont.get("ThroughputCapacity", 0)
        elif fs_type == "OPENZFS":
            ozfs = fs.get("OpenZFSConfiguration") or {}
            throughput_capacity = ozfs.get("ThroughputCapacity", 0)

        items.append({
            "file_system_id": fs["FileSystemId"],
            "customer_id": customer_id,
            "client_tag": client_tag,
            "file_system_type": fs_type,
            "lifecycle": fs.get("Lifecycle", ""),
            "storage_capacity_gb": storage_capacity,
            "storage_type": fs.get("StorageType", ""),
            "throughput_capacity_mbps": throughput_capacity,
            "dns_name": dns_name,
            "region": region,
            "vpc_id": fs.get("VpcId", ""),
            "owner_id": fs.get("OwnerId", ""),
            "creation_time": fs["CreationTime"].isoformat() if fs.get("CreationTime") else "",
            "last_synced_at": synced_at,
        })
    logger.info("Region %s: collected %d FSx file systems", region, len(items))
    return items


def lambda_handler(event: dict, context: Any) -> dict:
    synced_at = _utcnow_iso()
    regions = _get_regions()
    dynamo = _dynamo_resource()
    tbl_fsx = dynamo.Table(TABLE_FSX)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    existing_ids = _scan_existing_ids(tbl_fsx, "file_system_id")
    seen_ids: set[str] = set()
    cache: dict = {}
    totals = {"file_systems": 0, "deleted": 0}

    for region in regions:
        try:
            items = collect_fsx(region, synced_at, tbl_customers, cache)
            if items:
                _batch_write(tbl_fsx, items)
            totals["file_systems"] += len(items)
            seen_ids.update(i["file_system_id"] for i in items)
        except ClientError as exc:
            logger.error("Error processing region %s: %s", region, exc)

    stale = list(existing_ids - seen_ids)
    if stale:
        _batch_delete(tbl_fsx, "file_system_id", stale)
        totals["deleted"] = len(stale)

    logger.info("FSx sync complete: %s", totals)
    return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": totals})}

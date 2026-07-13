"""RDS & Aurora sync — scans all regions, upserts into DynamoDB."""

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
TABLE_INSTANCES = "RDSInstances"
TABLE_CLUSTERS = "RDSClusters"
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


def _paginate(client: Any, method: str, result_key: str, **kwargs: Any) -> list[dict]:
    paginator = client.get_paginator(method)
    items: list[dict] = []
    for page in paginator.paginate(**kwargs):
        items.extend(page.get(result_key, []))
    return items


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


def collect_rds_instances(region: str, synced_at: str, customers_table: Any, cache: dict) -> list[dict]:
    rds = boto3.client("rds", region_name=region)
    try:
        db_instances = _paginate(rds, "describe_db_instances", "DBInstances")
    except ClientError as exc:
        logger.warning("RDS describe_db_instances failed in %s: %s", region, exc)
        return []

    items: list[dict] = []
    for inst in db_instances:
        tags = _tag_map(inst.get("TagList"))
        client_tag = tags.get("Client", "")
        customer_id = _resolve_customer(customers_table, client_tag, cache)
        endpoint = inst.get("Endpoint") or {}
        items.append({
            "db_instance_id": inst["DBInstanceIdentifier"],
            "customer_id": customer_id,
            "client_tag": client_tag,
            "engine": inst.get("Engine", ""),
            "engine_version": inst.get("EngineVersion", ""),
            "status": inst.get("DBInstanceStatus", ""),
            "instance_class": inst.get("DBInstanceClass", ""),
            "region": region,
            "availability_zone": inst.get("AvailabilityZone", ""),
            "multi_az": inst.get("MultiAZ", False),
            "storage_gb": inst.get("AllocatedStorage", 0),
            "storage_type": inst.get("StorageType", ""),
            "encrypted": inst.get("StorageEncrypted", False),
            "endpoint_address": endpoint.get("Address", ""),
            "endpoint_port": endpoint.get("Port", 0),
            "db_cluster_id": inst.get("DBClusterIdentifier", ""),
            "instance_create_time": inst["InstanceCreateTime"].isoformat() if inst.get("InstanceCreateTime") else "",
            "last_synced_at": synced_at,
        })
    logger.info("Region %s: collected %d RDS instances", region, len(items))
    return items


def collect_rds_clusters(region: str, synced_at: str, customers_table: Any, cache: dict) -> list[dict]:
    rds = boto3.client("rds", region_name=region)
    try:
        clusters = _paginate(rds, "describe_db_clusters", "DBClusters")
    except ClientError as exc:
        logger.warning("RDS describe_db_clusters failed in %s: %s", region, exc)
        return []

    items: list[dict] = []
    for cl in clusters:
        tags = _tag_map(cl.get("TagList"))
        client_tag = tags.get("Client", "")
        customer_id = _resolve_customer(customers_table, client_tag, cache)
        items.append({
            "db_cluster_id": cl["DBClusterIdentifier"],
            "customer_id": customer_id,
            "client_tag": client_tag,
            "engine": cl.get("Engine", ""),
            "engine_version": cl.get("EngineVersion", ""),
            "status": cl.get("Status", ""),
            "region": region,
            "availability_zones": cl.get("AvailabilityZones", []),
            "multi_az": cl.get("MultiAZ", False),
            "member_count": len(cl.get("DBClusterMembers", [])),
            "endpoint": cl.get("Endpoint", ""),
            "reader_endpoint": cl.get("ReaderEndpoint", ""),
            "port": cl.get("Port", 0),
            "encrypted": cl.get("StorageEncrypted", False),
            "cluster_create_time": cl["ClusterCreateTime"].isoformat() if cl.get("ClusterCreateTime") else "",
            "last_synced_at": synced_at,
        })
    logger.info("Region %s: collected %d RDS clusters", region, len(items))
    return items


def lambda_handler(event: dict, context: Any) -> dict:
    synced_at = _utcnow_iso()
    regions = _get_regions()
    dynamo = _dynamo_resource()
    tbl_instances = dynamo.Table(TABLE_INSTANCES)
    tbl_clusters = dynamo.Table(TABLE_CLUSTERS)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    existing_instance_ids = _scan_existing_ids(tbl_instances, "db_instance_id")
    existing_cluster_ids = _scan_existing_ids(tbl_clusters, "db_cluster_id")
    seen_instance_ids: set[str] = set()
    seen_cluster_ids: set[str] = set()
    cache: dict = {}
    totals = {"instances": 0, "clusters": 0, "deleted_instances": 0, "deleted_clusters": 0}

    for region in regions:
        try:
            instances = collect_rds_instances(region, synced_at, tbl_customers, cache)
            if instances:
                _batch_write(tbl_instances, instances)
            totals["instances"] += len(instances)
            seen_instance_ids.update(i["db_instance_id"] for i in instances)

            clusters = collect_rds_clusters(region, synced_at, tbl_customers, cache)
            if clusters:
                _batch_write(tbl_clusters, clusters)
            totals["clusters"] += len(clusters)
            seen_cluster_ids.update(c["db_cluster_id"] for c in clusters)
        except ClientError as exc:
            logger.error("Error processing region %s: %s", region, exc)

    stale = list(existing_instance_ids - seen_instance_ids)
    if stale:
        _batch_delete(tbl_instances, "db_instance_id", stale)
        totals["deleted_instances"] = len(stale)

    stale = list(existing_cluster_ids - seen_cluster_ids)
    if stale:
        _batch_delete(tbl_clusters, "db_cluster_id", stale)
        totals["deleted_clusters"] = len(stale)

    logger.info("RDS sync complete: %s", totals)
    return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": totals})}

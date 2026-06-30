"""
AWS Lambda — EC2 Inventory Sync
================================
Collects EC2 instances, EBS volumes, and EBS snapshots across all enabled
AWS regions, then upserts the data into three DynamoDB tables:

    EC2Instances  /  EC2Volumes  /  EC2Snapshots

Each item is tagged with the value of the EC2 "Client" tag (if present) and
the resolved ``customer_id`` from the Customers table so that the web
application can show each user only their own resources.

Invoke schedule (recommended): EventBridge rule every 15–60 minutes.

Required IAM permissions for the Lambda execution role
-------------------------------------------------------
    ec2:DescribeInstances
    ec2:DescribeVolumes
    ec2:DescribeSnapshots
    ec2:DescribeRegions
    dynamodb:PutItem          (EC2Instances, EC2Volumes, EC2Snapshots)
    dynamodb:BatchWriteItem   (EC2Instances, EC2Volumes, EC2Snapshots)
    dynamodb:Query            (Customers / email-index)
    dynamodb:GetItem          (Customers)

Environment variables
---------------------
    DYNAMODB_REGION          AWS region where DynamoDB tables live (default: us-east-1)
    EC2_REGIONS              Comma-separated list of regions to scan.
                             If unset, all currently-enabled regions are scanned.
    OWNER_FILTER             Set to "self" (default) to restrict DescribeSnapshots
                             to snapshots owned by this account.  Set to "" to
                             include shared snapshots.
    DYNAMODB_ENDPOINT_URL    Override endpoint for local testing (e.g. DynamoDB Local).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
OWNER_FILTER: str = os.environ.get("OWNER_FILTER", "self")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

TABLE_INSTANCES = "EC2Instances"
TABLE_VOLUMES = "EC2Volumes"
TABLE_SNAPSHOTS = "EC2Snapshots"
TABLE_CUSTOMERS = "Customers"
CUSTOMER_EMAIL_INDEX = "email-index"

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


def _tag_map(tags: list[dict] | None) -> dict[str, str]:
    """Convert the EC2 Tags list to a plain {key: value} dict."""
    if not tags:
        return {}
    return {t["Key"]: t["Value"] for t in tags}


def _get_regions() -> list[str]:
    """Return the list of regions to scan, from env-var or EC2 API."""
    env_regions = os.environ.get("EC2_REGIONS", "").strip()
    if env_regions:
        return [r.strip() for r in env_regions.split(",") if r.strip()]
    ec2 = boto3.client("ec2", region_name="us-east-1")
    resp = ec2.describe_regions(Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}])
    return [r["RegionName"] for r in resp["Regions"]]


def _paginate(client: Any, method: str, result_key: str, **kwargs: Any) -> list[dict]:
    """Generic paginator that collects all pages into a flat list."""
    paginator = client.get_paginator(method)
    items: list[dict] = []
    for page in paginator.paginate(**kwargs):
        items.extend(page.get(result_key, []))
    return items


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


# ---------------------------------------------------------------------------
# Customer resolution
# ---------------------------------------------------------------------------


class CustomerCache:
    """Lazy cache: resolves a 'Client' tag value → customer_id via DynamoDB."""

    def __init__(self, customers_table: Any) -> None:
        self._table = customers_table
        # Map client_tag_value → customer_id (or None when not found).
        self._cache: dict[str, str | None] = {}

    def resolve(self, client_tag_value: str) -> str | None:
        """Return the customer_id for the given Client tag value, or None."""
        if client_tag_value in self._cache:
            return self._cache[client_tag_value]

        # Try treating the tag value as the customer_id directly.
        # If the record has a `resolves_to` field, follow it (e.g. an old tag
        # alias like "SERRG" that should map to "CENTRICITY-CA").
        try:
            resp = self._table.get_item(Key={"customer_id": client_tag_value})
            item = resp.get("Item")
            if item:
                canonical = item.get("resolves_to") or client_tag_value
                self._cache[client_tag_value] = canonical
                return canonical
        except ClientError:
            pass

        # Fall back: query the email-index in case the tag contains an email.
        try:
            resp = self._table.query(
                IndexName=CUSTOMER_EMAIL_INDEX,
                KeyConditionExpression=Key("email").eq(client_tag_value),
                Limit=1,
            )
            items = resp.get("Items", [])
            if items:
                cid = items[0]["customer_id"]
                self._cache[client_tag_value] = cid
                return cid
        except ClientError:
            pass

        logger.warning("No customer found for Client tag value: %s", client_tag_value)
        self._cache[client_tag_value] = None
        return None


# ---------------------------------------------------------------------------
# EC2 data collectors
# ---------------------------------------------------------------------------


def collect_instances(region: str, synced_at: str, cache: CustomerCache) -> list[dict]:
    """Return DynamoDB items for all EC2 instances in *region*."""
    ec2 = boto3.client("ec2", region_name=region)
    reservations = _paginate(ec2, "describe_instances", "Reservations")

    items: list[dict] = []
    for reservation in reservations:
        for inst in reservation.get("Instances", []):
            tags = _tag_map(inst.get("Tags"))
            client_tag = tags.get("Client", "")
            customer_id = (cache.resolve(client_tag) if client_tag else None) or "unassigned"

            placement = inst.get("Placement", {})
            state = inst.get("State", {}).get("Name", "unknown")

            item: dict[str, Any] = {
                "instance_id": inst["InstanceId"],
                "customer_id": customer_id,
                "client_tag": client_tag,
                "name_tag": tags.get("Name", ""),
                "state": state,
                "instance_type": inst.get("InstanceType", ""),
                "region": region,
                "availability_zone": placement.get("AvailabilityZone", ""),
                "public_ip": inst.get("PublicIpAddress", ""),
                "private_ip": inst.get("PrivateIpAddress", ""),
                "launch_time": inst["LaunchTime"].isoformat() if inst.get("LaunchTime") else "",
                "platform": inst.get("Platform", "linux"),
                "vpc_id": inst.get("VpcId", ""),
                "subnet_id": inst.get("SubnetId", ""),
                "image_id": inst.get("ImageId", ""),
                "key_name": inst.get("KeyName", ""),
                "tags": tags,
                "last_synced_at": synced_at,
            }
            items.append(item)

    logger.info("Region %s: collected %d instances", region, len(items))
    return items


def collect_volumes(region: str, synced_at: str, cache: CustomerCache) -> list[dict]:
    """Return DynamoDB items for all EBS volumes in *region*."""
    ec2 = boto3.client("ec2", region_name=region)
    volumes = _paginate(ec2, "describe_volumes", "Volumes")

    items: list[dict] = []
    for vol in volumes:
        tags = _tag_map(vol.get("Tags"))
        client_tag = tags.get("Client", "")
        customer_id = (cache.resolve(client_tag) if client_tag else None) or "unassigned"

        attachments = vol.get("Attachments", [])
        attached_instance_id = attachments[0].get("InstanceId", "") if attachments else ""
        attachment_state = attachments[0].get("State", "detached") if attachments else "detached"

        item: dict[str, Any] = {
            "volume_id": vol["VolumeId"],
            "customer_id": customer_id,
            "client_tag": client_tag,
            "state": vol.get("State", "unknown"),
            "size_gb": vol.get("Size", 0),
            "volume_type": vol.get("VolumeType", ""),
            "availability_zone": vol.get("AvailabilityZone", ""),
            "encrypted": vol.get("Encrypted", False),
            "iops": vol.get("Iops", 0),
            "throughput": vol.get("Throughput", 0),
            "attached_instance_id": attached_instance_id,
            "attachment_state": attachment_state,
            "create_time": vol["CreateTime"].isoformat() if vol.get("CreateTime") else "",
            "tags": tags,
            "last_synced_at": synced_at,
        }
        items.append(item)

    logger.info("Region %s: collected %d volumes", region, len(items))
    return items


def collect_snapshots(region: str, synced_at: str, cache: CustomerCache) -> list[dict]:
    """Return DynamoDB items for EBS snapshots in *region*."""
    ec2 = boto3.client("ec2", region_name=region)

    kwargs: dict[str, Any] = {}
    if OWNER_FILTER:
        kwargs["OwnerIds"] = [OWNER_FILTER]

    snapshots = _paginate(ec2, "describe_snapshots", "Snapshots", **kwargs)

    items: list[dict] = []
    for snap in snapshots:
        tags = _tag_map(snap.get("Tags"))
        client_tag = tags.get("Client", "")
        customer_id = (cache.resolve(client_tag) if client_tag else None) or "unassigned"

        item: dict[str, Any] = {
            "snapshot_id": snap["SnapshotId"],
            "customer_id": customer_id,
            "client_tag": client_tag,
            "state": snap.get("State", "unknown"),
            "volume_id": snap.get("VolumeId", ""),
            "size_gb": snap.get("VolumeSize", 0),
            "description": snap.get("Description", ""),
            "encrypted": snap.get("Encrypted", False),
            "owner_id": snap.get("OwnerId", ""),
            "progress": snap.get("Progress", ""),
            "start_time": snap["StartTime"].isoformat() if snap.get("StartTime") else "",
            "tags": tags,
        }
        items.append(item)

    logger.info("Region %s: collected %d snapshots", region, len(items))
    return items


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event: dict, context: Any) -> dict:  # noqa: ARG001
    """Entry point invoked by EventBridge or a manual test event."""
    synced_at = _utcnow_iso()
    regions = _get_regions()
    logger.info("Starting EC2 inventory sync across %d region(s): %s", len(regions), regions)

    dynamo = _dynamo_resource()
    tbl_instances = dynamo.Table(TABLE_INSTANCES)
    tbl_volumes = dynamo.Table(TABLE_VOLUMES)
    tbl_snapshots = dynamo.Table(TABLE_SNAPSHOTS)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    cache = CustomerCache(tbl_customers)

    totals = {"instances": 0, "volumes": 0, "snapshots": 0}

    for region in regions:
        try:
            instances = collect_instances(region, synced_at, cache)
            if instances:
                _batch_write(tbl_instances, instances)
            totals["instances"] += len(instances)

            volumes = collect_volumes(region, synced_at, cache)
            if volumes:
                _batch_write(tbl_volumes, volumes)
            totals["volumes"] += len(volumes)

            snapshots = collect_snapshots(region, synced_at, cache)
            if snapshots:
                _batch_write(tbl_snapshots, snapshots)
            totals["snapshots"] += len(snapshots)

        except ClientError as exc:
            # Log and continue so a single bad region doesn't abort the sync.
            logger.error("Error processing region %s: %s", region, exc)

    logger.info("Sync complete. Upserted: %s", totals)
    return {
        "statusCode": 200,
        "body": json.dumps({"synced_at": synced_at, "totals": totals}),
    }

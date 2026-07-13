"""AWS Backup sync — vaults and recent jobs, upserted into DynamoDB."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
TABLE_VAULTS = "BackupVaults"
TABLE_JOBS = "BackupJobs"
TABLE_CUSTOMERS = "Customers"
_BATCH_SIZE = 25
_JOB_DAYS = 90


def _dynamo_resource() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


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


def collect_vaults(region: str, synced_at: str, customers_table: Any, cache: dict) -> tuple[list[dict], dict[str, str]]:
    """Returns (vault_items, vault_name_to_customer_id map)."""
    backup = boto3.client("backup", region_name=region)
    try:
        resp = backup.list_backup_vaults()
        vaults = resp.get("BackupVaultList", [])
    except ClientError as exc:
        logger.warning("list_backup_vaults failed in %s: %s", region, exc)
        return [], {}

    items: list[dict] = []
    vault_customer_map: dict[str, str] = {}

    for v in vaults:
        vault_arn = v.get("BackupVaultArn", "")
        vault_name = v.get("BackupVaultName", "")

        # Try Client tag first; fall back to resolving the vault name itself as a customer_id
        try:
            tags_resp = backup.list_tags(ResourceArn=vault_arn)
            tags = tags_resp.get("Tags", {})
        except ClientError:
            tags = {}

        client_tag = tags.get("Client", "") or vault_name
        customer_id = _resolve_customer(customers_table, client_tag, cache)
        vault_customer_map[vault_name] = customer_id

        items.append({
            "vault_arn": vault_arn,
            "customer_id": customer_id,
            "client_tag": client_tag,
            "vault_name": vault_name,
            "region": region,
            "recovery_points": v.get("NumberOfRecoveryPoints", 0),
            "encryption_key_arn": v.get("EncryptionKeyArn", ""),
            "creation_date": v["CreationDate"].isoformat() if v.get("CreationDate") else "",
            "last_synced_at": synced_at,
        })
    logger.info("Region %s: collected %d backup vaults", region, len(items))
    return items, vault_customer_map


def collect_jobs(region: str, synced_at: str, vault_customer_map: dict[str, str]) -> list[dict]:
    backup = boto3.client("backup", region_name=region)
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=_JOB_DAYS)).isoformat()
    try:
        paginator = backup.get_paginator("list_backup_jobs")
        raw_jobs: list[dict] = []
        for page in paginator.paginate(ByCreatedAfter=cutoff):
            raw_jobs.extend(page.get("BackupJobs", []))
    except ClientError as exc:
        logger.warning("list_backup_jobs failed in %s: %s", region, exc)
        return []

    items: list[dict] = []
    for j in raw_jobs:
        vault_name = j.get("BackupVaultName", "")
        # Resolve customer from the vault → customer map built during vault sync
        customer_id = vault_customer_map.get(vault_name, "unassigned")
        items.append({
            "backup_job_id": j["BackupJobId"],
            "customer_id": customer_id,
            "vault_name": vault_name,
            "resource_name": j.get("ResourceName", ""),
            "resource_arn": j.get("ResourceArn", ""),
            "resource_type": j.get("ResourceType", ""),
            "state": j.get("State", ""),
            "status_message": j.get("StatusMessage", ""),
            "region": region,
            "backup_size_bytes": j.get("BackupSizeInBytes", 0),
            "creation_date": j["CreationDate"].isoformat() if j.get("CreationDate") else "",
            "completion_date": j["CompletionDate"].isoformat() if j.get("CompletionDate") else "",
            "last_synced_at": synced_at,
        })
    logger.info("Region %s: collected %d backup jobs", region, len(items))
    return items


def lambda_handler(event: dict, context: Any) -> dict:
    synced_at = _utcnow_iso()
    regions = _get_regions()
    dynamo = _dynamo_resource()
    tbl_vaults = dynamo.Table(TABLE_VAULTS)
    tbl_jobs = dynamo.Table(TABLE_JOBS)
    tbl_customers = dynamo.Table(TABLE_CUSTOMERS)

    existing_vault_arns = _scan_existing_ids(tbl_vaults, "vault_arn")
    existing_job_ids = _scan_existing_ids(tbl_jobs, "backup_job_id")
    seen_vault_arns: set[str] = set()
    seen_job_ids: set[str] = set()
    cache: dict = {}
    totals = {"vaults": 0, "jobs": 0, "deleted_vaults": 0, "deleted_jobs": 0}

    for region in regions:
        try:
            vaults, vault_customer_map = collect_vaults(region, synced_at, tbl_customers, cache)
            if vaults:
                _batch_write(tbl_vaults, vaults)
            totals["vaults"] += len(vaults)
            seen_vault_arns.update(v["vault_arn"] for v in vaults)

            jobs = collect_jobs(region, synced_at, vault_customer_map)
            if jobs:
                _batch_write(tbl_jobs, jobs)
            totals["jobs"] += len(jobs)
            seen_job_ids.update(j["backup_job_id"] for j in jobs)
        except ClientError as exc:
            logger.error("Error processing region %s: %s", region, exc)

    stale = list(existing_vault_arns - seen_vault_arns)
    if stale:
        _batch_delete(tbl_vaults, "vault_arn", stale)
        totals["deleted_vaults"] = len(stale)

    stale = list(existing_job_ids - seen_job_ids)
    if stale:
        _batch_delete(tbl_jobs, "backup_job_id", stale)
        totals["deleted_jobs"] = len(stale)

    logger.info("Backup sync complete: %s", totals)
    return {"statusCode": 200, "body": json.dumps({"synced_at": synced_at, "totals": totals})}

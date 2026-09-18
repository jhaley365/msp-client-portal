"""AWS inventory endpoints — EC2, RDS, Backup, FSx, Route 53, all scoped to the authenticated customer."""

from __future__ import annotations

import base64
import json
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, Query

from app.core.config import DYNAMODB_ENDPOINT_URL, DYNAMODB_REGION
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/inventory", tags=["inventory"])

_PAGE_SIZE = 50


def _table(name: str) -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs).Table(name)


def _encode_key(last_evaluated_key: dict) -> str:
    """Encode the full DynamoDB LastEvaluatedKey as a URL-safe token."""
    return base64.urlsafe_b64encode(json.dumps(last_evaluated_key).encode()).decode()


def _decode_key(token: str) -> dict:
    """Decode a pagination token back into a DynamoDB ExclusiveStartKey."""
    return json.loads(base64.urlsafe_b64decode(token.encode()))


def _query_customer(
    table_name: str,
    index_name: str,
    customer_id: str,
    last_key: str | None,
    sort_key_name: str = "last_synced_at",
) -> dict[str, Any]:
    tbl = _table(table_name)
    kwargs: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        try:
            kwargs["ExclusiveStartKey"] = _decode_key(last_key)
        except Exception:
            pass

    resp = tbl.query(**kwargs)
    lek = resp.get("LastEvaluatedKey")
    return {
        "items": resp.get("Items", []),
        "next_key": _encode_key(lek) if lek else None,
        "count": resp.get("Count", 0),
    }


def _count_customer(table_name: str, index_name: str, customer_id: str) -> int:
    tbl = _table(table_name)
    resp = tbl.query(
        IndexName=index_name,
        KeyConditionExpression=Key("customer_id").eq(customer_id),
        Select="COUNT",
    )
    return resp.get("Count", 0)


# ── Summary ──────────────────────────────────────────────────────────────────

@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    customer_id = user["customer_id"]
    return {
        "instances": _count_customer("EC2Instances", "customer_id-last_synced_at-index", customer_id),
        "volumes": _count_customer("EC2Volumes", "customer_id-last_synced_at-index", customer_id),
        "snapshots": _count_customer("EC2Snapshots", "customer_id-start_time-index", customer_id),
    }


# ── EC2 Instances ─────────────────────────────────────────────────────────────

@router.get("/instances")
def list_instances(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "EC2Instances", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("name_tag") or "").lower())
    return result


# ── Volumes ───────────────────────────────────────────────────────────────────

@router.get("/volumes")
def list_volumes(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    return _query_customer(
        "EC2Volumes", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )


# ── Snapshots ─────────────────────────────────────────────────────────────────

@router.get("/snapshots")
def list_snapshots(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    tbl = _table("EC2Snapshots")
    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-start_time-index",
        "KeyConditionExpression": Key("customer_id").eq(user["customer_id"]),
        "Limit": _PAGE_SIZE,
        "ScanIndexForward": False,
    }
    if last_key:
        try:
            kwargs["ExclusiveStartKey"] = _decode_key(last_key)
        except Exception:
            pass
    resp = tbl.query(**kwargs)
    lek = resp.get("LastEvaluatedKey")
    return {
        "items": resp.get("Items", []),
        "next_key": _encode_key(lek) if lek else None,
        "count": resp.get("Count", 0),
    }


# ── RDS Instances ─────────────────────────────────────────────────────────────

@router.get("/rds/instances")
def list_rds_instances(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "RDSInstances", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("db_instance_id") or "").lower())
    return result


# ── Aurora Clusters ───────────────────────────────────────────────────────────

@router.get("/rds/clusters")
def list_rds_clusters(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "RDSClusters", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("db_cluster_id") or "").lower())
    return result


# ── Backup Vaults ─────────────────────────────────────────────────────────────

@router.get("/backup/vaults")
def list_backup_vaults(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "BackupVaults", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("vault_name") or "").lower())
    return result


# ── Backup Jobs ───────────────────────────────────────────────────────────────

@router.get("/backup/jobs")
def list_backup_jobs(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    return _query_customer(
        "BackupJobs",
        "customer_id-creation_date-index",
        user["customer_id"],
        last_key,
        sort_key_name="creation_date",
    )


# ── FSx File Systems ──────────────────────────────────────────────────────────

@router.get("/fsx")
def list_fsx(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "FSxFileSystems", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("file_system_id") or "").lower())
    return result


# ── Backup Coverage ───────────────────────────────────────────────────────────

@router.get("/backup/coverage")
def list_backup_coverage(
    user: dict = Depends(get_current_user),
) -> dict:
    tbl = _table("BackupCoverage")
    items: list[Any] = []
    kwargs: dict[str, Any] = {
        "IndexName": "customer_id-checked_at-index",
        "KeyConditionExpression": Key("customer_id").eq(user["customer_id"]),
        "ScanIndexForward": False,
        "Limit": 500,
    }
    resp = tbl.query(**kwargs)
    # Deduplicate: keep only the most recent record per instance_id
    seen: set[str] = set()
    for item in resp.get("Items", []):
        iid = item["instance_id"]
        if iid not in seen:
            seen.add(iid)
            items.append(item)
    items.sort(key=lambda x: (x.get("is_covered", True), (x.get("instance_name") or "").lower()))
    return {"items": items, "count": len(items)}


# ── VPN Connections ───────────────────────────────────────────────────────────

@router.get("/vpn")
def list_vpn(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "VPNConnections", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("name") or "").lower())
    return result


# ── Route 53 Zones ────────────────────────────────────────────────────────────

@router.get("/route53")
def list_route53(
    last_key: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> dict:
    result = _query_customer(
        "Route53Zones", "customer_id-last_synced_at-index", user["customer_id"], last_key
    )
    result["items"] = sorted(result["items"], key=lambda x: (x.get("name") or "").lower())
    return result

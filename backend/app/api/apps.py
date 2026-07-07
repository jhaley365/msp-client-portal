"""Apps endpoints — XGuardian RDS SQL Server data."""

from __future__ import annotations

from typing import Any

import pymssql
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import RDS_DATABASE, RDS_HOST, RDS_PASSWORD, RDS_USER
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/apps", tags=["apps"])

TABLE = "AWS_EC2_VM_Titan"


def _conn() -> Any:
    if not RDS_HOST or not RDS_USER or not RDS_PASSWORD:
        raise HTTPException(status_code=503, detail="RDS connection not configured")
    return pymssql.connect(
        server=RDS_HOST,
        user=RDS_USER,
        password=RDS_PASSWORD,
        database=RDS_DATABASE,
        timeout=10,
    )


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)) -> dict:
    """Return card counts for Maestro, Titan, PA Sessions, DT Sessions."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT
                SUM(CASE WHEN [Group]=1 THEN 1 ELSE 0 END) AS titan_total,
                SUM(CASE WHEN [Group]=1 AND [LoggedOn]!='ASSIGNED' THEN 1 ELSE 0 END) AS titan_in_use,
                SUM(CASE WHEN [Group]=2 THEN 1 ELSE 0 END) AS maestro_total,
                SUM(CASE WHEN [Group]=2 AND [LoggedOn]!='ASSIGNED' THEN 1 ELSE 0 END) AS maestro_in_use,
                SUM(CASE WHEN [Name] NOT LIKE '%DT%' THEN 1 ELSE 0 END) AS pa_total,
                SUM(CASE WHEN [Name] NOT LIKE '%DT%' AND [LoggedOn]!='ASSIGNED' THEN 1 ELSE 0 END) AS pa_in_use,
                SUM(CASE WHEN [Name] LIKE '%DT%' THEN 1 ELSE 0 END) AS dt_total,
                SUM(CASE WHEN [Name] LIKE '%DT%' AND [LoggedOn]!='ASSIGNED' THEN 1 ELSE 0 END) AS dt_in_use
            FROM [{TABLE}]
        """)
        row = cur.fetchone()
    return {
        "titan_total":    int(row[0] or 0),
        "titan_in_use":   int(row[1] or 0),
        "maestro_total":  int(row[2] or 0),
        "maestro_in_use": int(row[3] or 0),
        "pa_total":       int(row[4] or 0),
        "pa_in_use":      int(row[5] or 0),
        "dt_total":       int(row[6] or 0),
        "dt_in_use":      int(row[7] or 0),
    }


@router.get("/instances")
def list_instances(user: dict = Depends(get_current_user)) -> dict:
    """Return all VM rows for the apps table."""
    with _conn() as conn:
        cur = conn.cursor(as_dict=True)
        cur.execute(f"""
            SELECT
                [Name],
                [PublicIPV4],
                [LocalIPV4],
                [LoggedOn],
                [Active],
                [Available],
                [Processing],
                [DomainJoined],
                [AzureAdJoined],
                [InstanceID],
                [CreateDate]
            FROM [{TABLE}]
            ORDER BY [Name]
        """)
        rows = cur.fetchall()

    items = []
    for r in rows:
        logged_on = r["LoggedOn"] or ""
        status = "Available" if logged_on.upper() == "ASSIGNED" else "In Use"
        items.append({
            "name":           r["Name"] or "",
            "public_ip":      r["PublicIPV4"] or "",
            "local_ip":       r["LocalIPV4"] or "",
            "logged_on":      logged_on,
            "status":         status,
            "processing":     bool(r["Processing"]),
            "domain_joined":  bool(r["DomainJoined"]),
            "azure_ad":       bool(r["AzureAdJoined"]),
            "instance_id":    r["InstanceID"] or "",
            "create_date":    str(r["CreateDate"]) if r["CreateDate"] else "",
        })

    return {"items": items, "count": len(items)}

"""
Backup Coverage Check
=====================
Compares EC2 instances against recent AWS Backup jobs.
Any running/stopped instance with no backup job in the last LOOKBACK_DAYS
is flagged as uncovered.  New gaps trigger an email alert to ALERT_EMAIL.

Run this after ec2_inventory_sync and backup_sync have completed.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

SMTP_HOST = "mail.smtp2go.com"
SMTP_PORT = 25
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@haley365.com")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "support@haley365.com")

# Instances with no backup job within this window are flagged as uncovered.
LOOKBACK_DAYS = int(os.environ.get("BACKUP_LOOKBACK_DAYS", "14"))

# States considered active enough to require a backup.
ACTIVE_STATES = {"running", "stopped"}

_BATCH_SIZE = 25


def _dynamo_resource() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _scan_all(table: Any, filter_expr=None) -> list[dict]:
    items: list[dict] = []
    kwargs: dict[str, Any] = {}
    if filter_expr is not None:
        kwargs["FilterExpression"] = filter_expr
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def _query_customer(table: Any, index: str, customer_id: str) -> list[dict]:
    items: list[dict] = []
    kwargs: dict[str, Any] = {
        "IndexName": index,
        "KeyConditionExpression": Key("customer_id").eq(customer_id),
    }
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return items


def _batch_write(table: Any, items: list[dict]) -> None:
    for i in range(0, len(items), _BATCH_SIZE):
        chunk = items[i: i + _BATCH_SIZE]
        requests = [{"PutRequest": {"Item": item}} for item in chunk]
        resp = table.meta.client.batch_write_item(RequestItems={table.name: requests})
        unprocessed = resp.get("UnprocessedItems", {}).get(table.name, [])
        if unprocessed:
            table.meta.client.batch_write_item(RequestItems={table.name: unprocessed})


def _instance_id_from_arn(arn: str) -> str:
    """Extract instance ID from an EC2 resource ARN."""
    # arn:aws:ec2:region:account:instance/i-xxxxx
    if "/i-" in arn:
        return "i-" + arn.split("/i-", 1)[1]
    return ""


def _send_alert_email(new_gaps: dict[str, list[dict]]) -> None:
    """Send a summary email listing newly uncovered instances grouped by customer."""
    if not new_gaps:
        return

    total = sum(len(v) for v in new_gaps.values())
    subject = f"[Haley365] Backup Coverage Alert — {total} unprotected instance{'s' if total != 1 else ''}"

    rows_html = ""
    rows_text = ""
    for customer_id, instances in sorted(new_gaps.items()):
        for inst in instances:
            name = inst.get("instance_name") or inst["instance_id"]
            rows_html += (
                f"<tr>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e2840'>{customer_id}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e2840'>{name}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e2840;font-family:monospace'>{inst['instance_id']}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e2840'>{inst.get('state','')}</td>"
                f"<td style='padding:6px 12px;border-bottom:1px solid #1e2840'>{inst.get('region','')}</td>"
                f"</tr>"
            )
            rows_text += f"  {customer_id} | {name} | {inst['instance_id']} | {inst.get('state','')} | {inst.get('region','')}\n"

    html_body = f"""
<div style="font-family:'IBM Plex Sans',system-ui,sans-serif;max-width:700px;margin:0 auto;padding:32px 24px;background:#0c111e;color:#eaf0fb;border-radius:12px">
  <div style="font-size:13px;font-weight:800;letter-spacing:0.14em;color:#fff;margin-bottom:4px">HALEY365</div>
  <div style="font-size:9px;letter-spacing:0.22em;color:#7f8ea3;margin-bottom:24px">CLIENT PORTAL — BACKUP ALERT</div>
  <p style="color:#eaf0fb;font-size:15px;margin:0 0 8px">
    <strong style="color:#f87171">{total} instance{'s' if total != 1 else ''}</strong> with no backup in the last {LOOKBACK_DAYS} days:
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:16px">
    <thead>
      <tr style="background:#0a0f1a;color:#7f8ea3;font-size:11px;letter-spacing:0.08em;text-transform:uppercase">
        <th style="padding:8px 12px;text-align:left">Customer</th>
        <th style="padding:8px 12px;text-align:left">Name</th>
        <th style="padding:8px 12px;text-align:left">Instance ID</th>
        <th style="padding:8px 12px;text-align:left">State</th>
        <th style="padding:8px 12px;text-align:left">Region</th>
      </tr>
    </thead>
    <tbody style="color:#eaf0fb">
      {rows_html}
    </tbody>
  </table>
  <p style="color:#7f8ea3;font-size:11.5px;margin:24px 0 0">
    View full coverage details in the Haley365 Client Portal → AWS → Coverage tab.
  </p>
</div>
"""
    text_body = (
        f"Haley365 Backup Coverage Alert\n"
        f"{'=' * 40}\n"
        f"{total} instance(s) with no backup in the last {LOOKBACK_DAYS} days:\n\n"
        f"  Customer | Name | Instance ID | State | Region\n"
        f"{rows_text}\n"
        f"View details in the Haley365 Client Portal → AWS → Coverage tab.\n"
    )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = ALERT_EMAIL
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.sendmail(SENDER_EMAIL, ALERT_EMAIL, msg.as_string())
        logger.info("Backup coverage alert sent to %s (%d gaps)", ALERT_EMAIL, total)
    except Exception as exc:
        logger.error("Failed to send backup coverage alert: %s", exc)


def lambda_handler(event: dict, context: Any) -> dict:
    checked_at = _utcnow_iso()
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()

    dynamo = _dynamo_resource()
    tbl_instances = dynamo.Table("EC2Instances")
    tbl_jobs = dynamo.Table("BackupJobs")
    tbl_coverage = dynamo.Table("BackupCoverage")

    # Load existing coverage records to detect NEW gaps
    existing_coverage = {r["instance_id"]: r for r in _scan_all(tbl_coverage)}
    previously_uncovered = {
        iid for iid, r in existing_coverage.items() if not r.get("is_covered")
    }

    # Collect all active instances
    from boto3.dynamodb.conditions import Attr
    all_instances = _scan_all(
        tbl_instances,
        filter_expr=Attr("state").is_in(list(ACTIVE_STATES))
    )
    logger.info("Found %d active instances to check", len(all_instances))

    # Collect all SUCCESSFUL EC2 backup jobs newer than cutoff.
    # Failed/aborted jobs do not count as coverage.
    successful_states = ["COMPLETED", "COMPLETED_WITH_ISSUES"]
    all_jobs = _scan_all(
        tbl_jobs,
        filter_expr=(
            Attr("resource_type").eq("EC2")
            & Attr("creation_date").gte(cutoff)
            & Attr("state").is_in(successful_states)
        )
    )

    # Build set of backed-up instance IDs and their most recent job info
    backed_up: dict[str, dict] = {}
    for job in all_jobs:
        iid = _instance_id_from_arn(job.get("resource_arn", ""))
        if not iid:
            continue
        existing = backed_up.get(iid)
        if not existing or job.get("creation_date", "") > existing.get("creation_date", ""):
            backed_up[iid] = job

    # Build coverage records
    coverage_items: list[dict] = []
    new_gaps: dict[str, list[dict]] = {}

    for inst in all_instances:
        iid = inst["instance_id"]
        customer_id = inst.get("customer_id", "unassigned")
        last_job = backed_up.get(iid)
        is_covered = last_job is not None

        prev = existing_coverage.get(iid)
        first_detected_at = (
            prev.get("first_detected_at", checked_at) if prev else checked_at
        ) if not is_covered else ""

        coverage_items.append({
            "instance_id": iid,
            "customer_id": customer_id,
            "instance_name": inst.get("name_tag", ""),
            "state": inst.get("state", ""),
            "region": inst.get("region", ""),
            "is_covered": is_covered,
            "last_backup_date": last_job.get("creation_date", "") if last_job else "",
            "last_backup_job_id": last_job.get("backup_job_id", "") if last_job else "",
            "first_detected_at": first_detected_at,
            "checked_at": checked_at,
        })

        # Collect newly uncovered instances for the alert email
        if not is_covered and iid not in previously_uncovered:
            new_gaps.setdefault(customer_id, []).append({
                "instance_id": iid,
                "instance_name": inst.get("name_tag", ""),
                "state": inst.get("state", ""),
                "region": inst.get("region", ""),
            })

    if coverage_items:
        _batch_write(tbl_coverage, coverage_items)

    # Remove coverage records for instances that no longer exist in EC2Instances
    active_instance_ids = {inst["instance_id"] for inst in all_instances}
    stale_coverage_ids = [
        iid for iid in existing_coverage if iid not in active_instance_ids
    ]
    if stale_coverage_ids:
        logger.info("Deleting %d stale coverage records", len(stale_coverage_ids))
        for i in range(0, len(stale_coverage_ids), _BATCH_SIZE):
            chunk = stale_coverage_ids[i: i + _BATCH_SIZE]
            requests = [{"DeleteRequest": {"Key": {"instance_id": iid}}} for iid in chunk]
            tbl_coverage.meta.client.batch_write_item(RequestItems={tbl_coverage.name: requests})

    covered_count = sum(1 for r in coverage_items if r["is_covered"])
    uncovered_count = len(coverage_items) - covered_count
    new_gap_count = sum(len(v) for v in new_gaps.values())

    logger.info(
        "Coverage check complete: %d covered, %d uncovered, %d new gaps, %d stale deleted",
        covered_count, uncovered_count, new_gap_count, len(stale_coverage_ids),
    )

    if new_gaps:
        _send_alert_email(new_gaps)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "checked_at": checked_at,
            "lookback_days": LOOKBACK_DAYS,
            "totals": {
                "instances_checked": len(coverage_items),
                "covered": covered_count,
                "uncovered": uncovered_count,
                "new_gaps_alerted": new_gap_count,
                "stale_deleted": len(stale_coverage_ids),
            },
        }),
    }

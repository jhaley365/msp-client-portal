"""
Migrate existing Customers records into the new Users table.

Creates one User per Customer record that has an email address.
Safe to re-run — skips emails that already exist in Users.

Usage:
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/migrate_customers_to_users.py
"""

from __future__ import annotations

import os
import boto3

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def main() -> None:
    kwargs = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    dynamo = boto3.resource("dynamodb", **kwargs)
    customers_tbl = dynamo.Table("Customers")
    users_tbl = dynamo.Table("Users")

    # Scan all customers
    items: list[dict] = []
    scan_kwargs: dict = {}
    while True:
        resp = customers_tbl.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    created = skipped = 0
    for item in items:
        email = item.get("email", "").lower().strip()
        customer_id = item.get("customer_id", "")
        if not email or not customer_id:
            continue

        # Check if already migrated
        existing = users_tbl.query(
            IndexName="email-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("email").eq(email),
            Limit=1,
        ).get("Items", [])

        if existing:
            print(f"  SKIP  {email} (already in Users)")
            skipped += 1
            continue

        import uuid
        from datetime import datetime, timezone
        user_id = str(uuid.uuid4())
        users_tbl.put_item(Item={
            "user_id": user_id,
            "email": email,
            "customer_id": customer_id,
            "name": item.get("name", ""),
            "is_admin": bool(item.get("is_admin", False)),
            "is_active": bool(item.get("is_active", True)),
            "created_at": item.get("created_at", datetime.now(tz=timezone.utc).isoformat()),
        })
        print(f"  CREATE {email} → customer {customer_id}")
        created += 1

    print(f"\nDone. Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    main()

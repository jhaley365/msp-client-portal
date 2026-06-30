"""
Map a ScoutDNS organization UUID to a portal customer.

Sets the `scoutdns_org_id` attribute on the Customers DynamoDB table.

Usage:
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/scoutdns_map_customer.py \\
        --customer-id <customer_id> --org-id <scoutdns_org_uuid>

Run scoutdns_list_orgs.py first to get the org UUIDs.
"""

from __future__ import annotations

import argparse
import os

import boto3

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Map ScoutDNS org to portal customer")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--org-id", required=True, help="ScoutDNS organization UUID")
    args = parser.parse_args()

    kwargs = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    dynamo = boto3.resource("dynamodb", **kwargs)
    tbl = dynamo.Table("Customers")

    tbl.update_item(
        Key={"customer_id": args.customer_id},
        UpdateExpression="SET scoutdns_org_id = :v",
        ExpressionAttributeValues={":v": args.org_id},
    )
    print(f"Mapped customer {args.customer_id} → ScoutDNS org {args.org_id}")


if __name__ == "__main__":
    main()

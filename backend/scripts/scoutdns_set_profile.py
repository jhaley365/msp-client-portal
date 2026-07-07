"""
Set the scoutdns_profile on a portal customer record.

This profile name must match the Profile field in ScoutDNS roaming clients
exactly (case-insensitive). Clients are filtered by this profile during sync.

Usage:
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/scoutdns_set_profile.py \\
        --customer-id FPC --profile "FPC-Users"
"""

from __future__ import annotations

import argparse
import os

import boto3

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Set ScoutDNS profile filter for a customer")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--profile", required=True, help='Profile name as shown in ScoutDNS, e.g. "FPC-Users"')
    args = parser.parse_args()

    kwargs: dict = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    tbl = boto3.resource("dynamodb", **kwargs).Table("Customers")

    tbl.update_item(
        Key={"customer_id": args.customer_id},
        UpdateExpression="SET scoutdns_profile = :p",
        ExpressionAttributeValues={":p": args.profile},
    )
    print(f"Set scoutdns_profile={args.profile!r} on customer {args.customer_id!r}")


if __name__ == "__main__":
    main()

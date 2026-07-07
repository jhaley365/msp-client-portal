"""
Set the xguardian_prefix on a portal customer record.

The prefix is the VM name prefix used in the XGuardian database
(e.g. "FPC" for FPC-TITAN-1, "TCC" for TCC-TITAN-1).

Usage:
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/xguardian_map_customer.py \\
        --customer-id FPC --prefix FPC
"""

from __future__ import annotations

import argparse
import os

import boto3

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Map a customer to an XGuardian VM name prefix")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--prefix", required=True, help="VM name prefix, e.g. FPC or TCC")
    args = parser.parse_args()

    kwargs: dict = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    tbl = boto3.resource("dynamodb", **kwargs).Table("Customers")

    tbl.update_item(
        Key={"customer_id": args.customer_id},
        UpdateExpression="SET xguardian_prefix = :p",
        ExpressionAttributeValues={":p": args.prefix.upper()},
    )
    print(f"Set xguardian_prefix={args.prefix.upper()!r} on customer {args.customer_id!r}")


if __name__ == "__main__":
    main()

"""
Store O365 app registration credentials on a portal customer record.

Usage:
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/o365_add_customer.py \\
        --customer-id <customer_id> \\
        --tenant-id <azure_tenant_id> \\
        --client-id <app_client_id> \\
        --client-secret <app_client_secret>

Find tenant_id and client_id in the Azure portal under:
    Azure Active Directory → App registrations → <your app> → Overview
Find client_secret under:
    Certificates & secrets → Client secrets
"""

from __future__ import annotations

import argparse
import os

import boto3

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Add O365 credentials to a portal customer")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--tenant-id", required=True, help="Azure AD tenant ID (GUID)")
    parser.add_argument("--client-id", required=True, help="App registration client ID (GUID)")
    parser.add_argument("--client-secret", required=True, help="App registration client secret value")
    args = parser.parse_args()

    kwargs = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    tbl = boto3.resource("dynamodb", **kwargs).Table("Customers")

    tbl.update_item(
        Key={"customer_id": args.customer_id},
        UpdateExpression="SET o365_tenant_id = :t, o365_client_id = :c, o365_client_secret = :s",
        ExpressionAttributeValues={
            ":t": args.tenant_id,
            ":c": args.client_id,
            ":s": args.client_secret,
        },
    )
    print(f"O365 credentials stored for customer {args.customer_id}")
    print(f"  Tenant ID:  {args.tenant_id}")
    print(f"  Client ID:  {args.client_id}")
    print(f"  Secret:     {'*' * 8}{args.client_secret[-4:]}")


if __name__ == "__main__":
    main()

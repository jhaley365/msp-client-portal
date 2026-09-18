"""
Set the huntress_org_name on a portal customer in DynamoDB.

Usage:
    PYTHONPATH=./backend python backend/scripts/huntress_map_customer.py \
        --customer-id FPC \
        --org-name "Foley Products"

Required env vars: AWS credentials (or IAM role on EC2)
Optional env vars: DYNAMODB_REGION (default us-east-1), DYNAMODB_ENDPOINT_URL
"""

import argparse
import os
import boto3

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def update(customer_id: str, org_name: str) -> None:
    kwargs = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    table = boto3.resource("dynamodb", **kwargs).Table("Customers")

    resp = table.update_item(
        Key={"customer_id": customer_id},
        UpdateExpression="SET huntress_org_name = :n",
        ExpressionAttributeValues={":n": org_name},
        ReturnValues="UPDATED_NEW",
    )
    print(f"Updated customer '{customer_id}' → huntress_org_name = '{org_name}'")
    print(f"  DynamoDB response: {resp['Attributes']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map a portal customer to their Huntress org name")
    parser.add_argument("--customer-id", required=True, help="Portal customer_id (e.g. FPC)")
    parser.add_argument("--org-name", required=True, help="Exact Huntress organization name")
    args = parser.parse_args()
    update(args.customer_id, args.org_name)

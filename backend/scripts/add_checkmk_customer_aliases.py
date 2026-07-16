"""Add CheckMK host group → portal customer_id alias records to the Customers table."""

import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

kwargs = {"region_name": REGION}
if ENDPOINT:
    kwargs["endpoint_url"] = ENDPOINT

table = boto3.resource("dynamodb", **kwargs).Table("Customers")

# CheckMK group name → portal customer_id
ALIASES = [
    ("Bickerstaff", "BPRE"),
    ("Kidsteeth", "KID"),
    ("StudioBGP", "SBGP"),
]

for group_name, customer_id in ALIASES:
    try:
        table.put_item(Item={
            "customer_id": group_name,
            "resolves_to": customer_id,
            "name": f"Alias: {group_name} → {customer_id}",
        })
        print(f"Added alias: {group_name} → {customer_id}")
    except ClientError as e:
        print(f"Error adding {group_name}: {e}")

"""Create VPNConnections DynamoDB table."""

import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

kwargs = {"region_name": REGION}
if ENDPOINT:
    kwargs["endpoint_url"] = ENDPOINT

client = boto3.client("dynamodb", **kwargs)

try:
    client.create_table(
        TableName="VPNConnections",
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "vpn_id", "AttributeType": "S"},
            {"AttributeName": "customer_id", "AttributeType": "S"},
            {"AttributeName": "last_synced_at", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "vpn_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "customer_id-last_synced_at-index",
                "KeySchema": [
                    {"AttributeName": "customer_id", "KeyType": "HASH"},
                    {"AttributeName": "last_synced_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
    print("Created VPNConnections")
    client.get_waiter("table_exists").wait(TableName="VPNConnections")
    print("VPNConnections is active")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print("VPNConnections already exists, skipping")
    else:
        raise

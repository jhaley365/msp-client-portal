"""Create FSxFileSystems DynamoDB table."""

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
        TableName="FSxFileSystems",
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "file_system_id", "AttributeType": "S"},
            {"AttributeName": "customer_id", "AttributeType": "S"},
            {"AttributeName": "last_synced_at", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "file_system_id", "KeyType": "HASH"}],
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
    print("Created FSxFileSystems")
    client.get_waiter("table_exists").wait(TableName="FSxFileSystems")
    print("FSxFileSystems is active")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print("FSxFileSystems already exists, skipping")
    else:
        raise

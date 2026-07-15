"""Create BackupCoverage DynamoDB table."""

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
        TableName="BackupCoverage",
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "instance_id", "AttributeType": "S"},
            {"AttributeName": "customer_id", "AttributeType": "S"},
            {"AttributeName": "checked_at", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "instance_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "customer_id-checked_at-index",
                "KeySchema": [
                    {"AttributeName": "customer_id", "KeyType": "HASH"},
                    {"AttributeName": "checked_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
    print("Created BackupCoverage")
    client.get_waiter("table_exists").wait(TableName="BackupCoverage")
    print("BackupCoverage is active")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print("BackupCoverage already exists, skipping")
    else:
        raise

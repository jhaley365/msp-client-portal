"""Create CheckMKHosts and CheckMKServices DynamoDB tables."""

import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

kwargs = {"region_name": REGION}
if ENDPOINT:
    kwargs["endpoint_url"] = ENDPOINT

client = boto3.client("dynamodb", **kwargs)

TABLES = [
    {
        "TableName": "CheckMKHosts",
        "pk": "host_name",
        "gsi_sort": "last_synced_at",
        "gsi_name": "customer_id-last_synced_at-index",
    },
    {
        "TableName": "CheckMKServices",
        "pk": "service_key",
        "gsi_sort": "last_synced_at",
        "gsi_name": "customer_id-last_synced_at-index",
    },
]

for tbl in TABLES:
    try:
        client.create_table(
            TableName=tbl["TableName"],
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": tbl["pk"], "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": tbl["gsi_sort"], "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": tbl["pk"], "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": tbl["gsi_name"],
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                        {"AttributeName": tbl["gsi_sort"], "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        print(f"Created {tbl['TableName']}")
        client.get_waiter("table_exists").wait(TableName=tbl["TableName"])
        print(f"{tbl['TableName']} is active")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"{tbl['TableName']} already exists, skipping")
        else:
            raise

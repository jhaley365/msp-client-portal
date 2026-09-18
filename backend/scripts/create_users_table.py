"""
Create the Users DynamoDB table.

Usage:
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/create_users_table.py
"""

from __future__ import annotations

import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("DYNAMODB_REGION", "us-east-1")
ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT_URL") or None


def main() -> None:
    kwargs = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    client = boto3.client("dynamodb", **kwargs)

    try:
        client.create_table(
            TableName="Users",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "email",   "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "email-index",
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        print("Users table created.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            print("Users table already exists — nothing to do.")
        else:
            raise


if __name__ == "__main__":
    main()

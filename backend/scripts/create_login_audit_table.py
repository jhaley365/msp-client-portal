"""
Create the LoginAudit DynamoDB table.

Usage:
    PYTHONPATH=backend python backend/scripts/create_login_audit_table.py
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
            TableName="LoginAudit",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "login_id",    "AttributeType": "S"},
                {"AttributeName": "customer_id", "AttributeType": "S"},
                {"AttributeName": "logged_in_at","AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "login_id", "KeyType": "HASH"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "customer_id-logged_in_at-index",
                    "KeySchema": [
                        {"AttributeName": "customer_id", "KeyType": "HASH"},
                        {"AttributeName": "logged_in_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        print("LoginAudit table created.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            print("LoginAudit table already exists — nothing to do.")
        else:
            raise


if __name__ == "__main__":
    main()

"""
Customer management helpers used by the web application backend.

Passwords are stored as bcrypt hashes — never plaintext.
The ``bcrypt`` package must be present in the Lambda/server deployment:
    pip install bcrypt

DynamoDB table: Customers
    PK:  customer_id  (UUID)
    GSI: email-index  (email → customer_id)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import bcrypt
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

DYNAMODB_REGION: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
_ENDPOINT: str | None = os.environ.get("DYNAMODB_ENDPOINT_URL") or None
TABLE_CUSTOMERS = "Customers"
CUSTOMER_EMAIL_INDEX = "email-index"

# Bcrypt work factor — increase over time as hardware improves.
_BCRYPT_ROUNDS = 12


def _table() -> Any:
    kwargs: dict[str, Any] = {"region_name": DYNAMODB_REGION}
    if _ENDPOINT:
        kwargs["endpoint_url"] = _ENDPOINT
    return boto3.resource("dynamodb", **kwargs).Table(TABLE_CUSTOMERS)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plaintext: str) -> str:
    """Return a bcrypt hash string for *plaintext*."""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True when *plaintext* matches the stored bcrypt *hashed* value."""
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_customer(email: str, password: str, name: str = "", customer_id: str | None = None) -> dict:
    """
    Create a new customer record.

    Parameters
    ----------
    customer_id:
        Optional explicit ID.  When provided (e.g. the EC2 "Client" tag value
        such as "CENTRICITY-CA") it is used as the DynamoDB primary key so the
        inventory sync can resolve tag values directly.  When omitted a UUID is
        generated automatically.

    Returns the created item dict.
    Raises ``ValueError`` if the email is already registered.
    """
    tbl = _table()

    # Enforce unique email.
    existing = get_customer_by_email(email)
    if existing:
        raise ValueError(f"Email already registered: {email}")

    customer_id = customer_id or str(uuid.uuid4())
    item = {
        "customer_id": customer_id,
        "email": email.lower().strip(),
        "password_hash": hash_password(password),
        "name": name,
        "is_active": True,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    tbl.put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(customer_id)",
    )
    logger.info("Created customer %s (%s)", customer_id, email)
    # Return a copy without the password hash.
    return _safe(item)


def get_customer_by_email(email: str) -> dict | None:
    """Look up a customer by email address (case-insensitive). Returns None if not found."""
    tbl = _table()
    try:
        resp = tbl.query(
            IndexName=CUSTOMER_EMAIL_INDEX,
            KeyConditionExpression=Key("email").eq(email.lower().strip()),
            Limit=1,
        )
        items = resp.get("Items", [])
        return items[0] if items else None
    except ClientError as exc:
        logger.error("Error querying customer by email: %s", exc)
        raise


def get_customer_by_id(customer_id: str) -> dict | None:
    """Fetch a customer record by primary key. Returns None if not found."""
    tbl = _table()
    try:
        resp = tbl.get_item(Key={"customer_id": customer_id})
        return resp.get("Item")
    except ClientError as exc:
        logger.error("Error fetching customer %s: %s", customer_id, exc)
        raise


def authenticate(email: str, password: str) -> dict | None:
    """
    Verify credentials.

    Returns the customer item (without password_hash) on success,
    or None on failure.
    """
    item = get_customer_by_email(email)
    if not item:
        return None
    if not item.get("is_active", False):
        return None
    if not verify_password(password, item["password_hash"]):
        return None
    return _safe(item)


def _safe(item: dict) -> dict:
    """Return a copy of *item* with the password_hash removed."""
    return {k: v for k, v in item.items() if k != "password_hash"}

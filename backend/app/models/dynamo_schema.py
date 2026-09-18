"""
DynamoDB table schemas and GSI definitions for the MSP client portal.

Table design follows a single-table-per-entity pattern (one table per
entity type) rather than a monolithic single-table design, because:
  - Each entity is synced from a different third-party source on its own schedule.
  - Keeping tables separate makes IAM least-privilege and per-table capacity
    tuning straightforward.
  - All GSIs include tenant_id as the partition key so queries are always
    scoped to a single tenant.

Access patterns covered by GSIs
────────────────────────────────
Tenants
  • Look up by syncro_customer_id   → GSI: syncro_customer_id-index
  • Look up by aws_account_id       → GSI: aws_account_id-index

Tickets
  • All tickets for a tenant        → GSI: tenant_id-created_at-index  (PK=tenant_id, SK=created_at)
  • Tickets by status per tenant    → GSI: tenant_id-status-index       (PK=tenant_id, SK=status)
  • Tickets by assigned tech        → GSI: tenant_id-assigned_tech-index

SecurityIncidents
  • Incidents for a tenant by time  → GSI: tenant_id-detected_at-index
  • Incidents by severity           → GSI: tenant_id-severity-index
  • Incidents by status             → GSI: tenant_id-status-index

DnsEvents
  • Events for a tenant by time     → GSI: tenant_id-timestamp-index
  • Events by action (blocked/...)  → GSI: tenant_id-action-index
  • Events by domain                → GSI: tenant_id-domain-index
"""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Billing / capacity defaults
# ---------------------------------------------------------------------------

_PAY_PER_REQUEST = {"BillingMode": "PAY_PER_REQUEST"}


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

TENANTS_TABLE: dict[str, Any] = {
    "TableName": "Tenants",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "tenant_id", "AttributeType": "S"},
        {"AttributeName": "syncro_customer_id", "AttributeType": "S"},
        {"AttributeName": "aws_account_id", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "tenant_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # Look up a tenant by their Syncro CRM customer ID.
            "IndexName": "syncro_customer_id-index",
            "KeySchema": [
                {"AttributeName": "syncro_customer_id", "KeyType": "HASH"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Look up a tenant by their linked AWS account.
            "IndexName": "aws_account_id-index",
            "KeySchema": [
                {"AttributeName": "aws_account_id", "KeyType": "HASH"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}

TICKETS_TABLE: dict[str, Any] = {
    "TableName": "Tickets",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "ticket_id", "AttributeType": "S"},
        {"AttributeName": "tenant_id", "AttributeType": "S"},
        {"AttributeName": "created_at", "AttributeType": "S"},  # ISO-8601
        {"AttributeName": "status", "AttributeType": "S"},
        {"AttributeName": "assigned_tech", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "ticket_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All tickets for a tenant, sorted newest-first (reverse SK sort).
            "IndexName": "tenant_id-created_at-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Tickets filtered by status within a tenant (open, closed, …).
            "IndexName": "tenant_id-status-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "status", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Tickets assigned to a specific technician within a tenant.
            "IndexName": "tenant_id-assigned_tech-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "assigned_tech", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "ticket_id",
                    "subject",
                    "status",
                    "priority",
                    "created_at",
                    "updated_at",
                    "customer_name",
                ],
            },
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}

SECURITY_INCIDENTS_TABLE: dict[str, Any] = {
    "TableName": "SecurityIncidents",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "incident_id", "AttributeType": "S"},
        {"AttributeName": "tenant_id", "AttributeType": "S"},
        {"AttributeName": "detected_at", "AttributeType": "S"},  # ISO-8601
        {"AttributeName": "severity", "AttributeType": "S"},
        {"AttributeName": "status", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "incident_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All incidents for a tenant sorted by detection time.
            "IndexName": "tenant_id-detected_at-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "detected_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Incidents grouped by severity (critical, high, medium, low).
            "IndexName": "tenant_id-severity-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "severity", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Incidents filtered by status (open, investigating, resolved).
            "IndexName": "tenant_id-status-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "status", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "incident_id",
                    "severity",
                    "description",
                    "host_name",
                    "detected_at",
                    "resolved_at",
                ],
            },
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}

DNS_EVENTS_TABLE: dict[str, Any] = {
    "TableName": "DnsEvents",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "event_id", "AttributeType": "S"},
        {"AttributeName": "tenant_id", "AttributeType": "S"},
        {"AttributeName": "timestamp", "AttributeType": "S"},  # ISO-8601
        {"AttributeName": "action", "AttributeType": "S"},
        {"AttributeName": "domain", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "event_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # Time-range queries: all DNS events for a tenant in a window.
            "IndexName": "tenant_id-timestamp-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Filter by action (blocked / allowed) per tenant.
            "IndexName": "tenant_id-action-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "action", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "event_id",
                    "domain",
                    "category",
                    "timestamp",
                    "client_ip",
                ],
            },
        },
        {
            # Look up all events for a specific domain within a tenant.
            "IndexName": "tenant_id-domain-index",
            "KeySchema": [
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "domain", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "event_id",
                    "category",
                    "action",
                    "timestamp",
                    "client_ip",
                ],
            },
        },
    ],
    # High-volume table: consider enabling TTL on older events.
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}

CUSTOMERS_TABLE: dict[str, Any] = {
    "TableName": "Customers",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "email", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "customer_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # Look up a customer by email address (used during login).
            "IndexName": "email-index",
            "KeySchema": [
                {"AttributeName": "email", "KeyType": "HASH"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Fields stored per item (not indexed, so not in AttributeDefinitions):
#   password_hash  str   bcrypt hash of the user's password
#   name           str   display name
#   is_active      bool  soft-delete flag
#   created_at     str   ISO-8601

EC2_INSTANCES_TABLE: dict[str, Any] = {
    "TableName": "EC2Instances",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "instance_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "state", "AttributeType": "S"},
        {"AttributeName": "last_synced_at", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "instance_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All instances belonging to a customer, sorted by sync time.
            "IndexName": "customer_id-last_synced_at-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "last_synced_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Filter a customer's instances by state (running, stopped, …).
            "IndexName": "customer_id-state-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "state", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "instance_id",
                    "instance_type",
                    "region",
                    "private_ip",
                    "public_ip",
                    "client_tag",
                    "last_synced_at",
                ],
            },
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Additional fields stored per item:
#   client_tag        str   value of the EC2 "Client" tag
#   instance_type     str   e.g. "t3.medium"
#   region            str   e.g. "us-east-1"
#   availability_zone str
#   public_ip         str   may be absent
#   private_ip        str
#   launch_time       str   ISO-8601
#   platform          str   "windows" | "linux" | ""
#   vpc_id            str
#   subnet_id         str
#   image_id          str   AMI id
#   key_name          str
#   tags              map   all raw EC2 tags as key→value

EC2_VOLUMES_TABLE: dict[str, Any] = {
    "TableName": "EC2Volumes",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "volume_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "state", "AttributeType": "S"},
        {"AttributeName": "last_synced_at", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "volume_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All volumes for a customer, sorted by sync time.
            "IndexName": "customer_id-last_synced_at-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "last_synced_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Filter a customer's volumes by state (available, in-use, …).
            "IndexName": "customer_id-state-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "state", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "volume_id",
                    "size_gb",
                    "volume_type",
                    "availability_zone",
                    "encrypted",
                    "attached_instance_id",
                    "client_tag",
                    "last_synced_at",
                ],
            },
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Additional fields stored per item:
#   client_tag           str   value of the EC2 "Client" tag
#   size_gb              int
#   volume_type          str   gp3 | gp2 | io1 | st1 | sc1 | standard
#   availability_zone    str
#   encrypted            bool
#   iops                 int   may be absent
#   throughput           int   MiB/s, may be absent
#   attached_instance_id str   empty string when not attached
#   attachment_state     str   attached | detached | attaching | detaching
#   create_time          str   ISO-8601
#   tags                 map   all raw EC2 tags

EC2_SNAPSHOTS_TABLE: dict[str, Any] = {
    "TableName": "EC2Snapshots",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "snapshot_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "state", "AttributeType": "S"},
        {"AttributeName": "start_time", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "snapshot_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All snapshots for a customer sorted by creation time.
            "IndexName": "customer_id-start_time-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "start_time", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Filter a customer's snapshots by state (pending, completed, error).
            "IndexName": "customer_id-state-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "state", "KeyType": "RANGE"},
            ],
            "Projection": {
                "ProjectionType": "INCLUDE",
                "NonKeyAttributes": [
                    "snapshot_id",
                    "volume_id",
                    "size_gb",
                    "description",
                    "encrypted",
                    "progress",
                    "client_tag",
                    "start_time",
                ],
            },
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Additional fields stored per item:
#   client_tag    str   value of the EC2 "Client" tag
#   volume_id     str   source volume
#   size_gb       int
#   description   str
#   encrypted     bool
#   owner_id      str   AWS account id
#   progress      str   "100%" when complete
#   tags          map   all raw EC2 tags


SYNCRO_TICKETS_TABLE: dict[str, Any] = {
    "TableName": "SyncroTickets",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "ticket_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "created_at", "AttributeType": "S"},  # ISO-8601
        {"AttributeName": "status", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "ticket_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All Syncro tickets for a customer, sorted by creation time.
            "IndexName": "customer_id-created_at-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Syncro tickets filtered by status within a customer.
            "IndexName": "customer_id-status-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "status", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Additional fields stored per item:
#   customer_name   str   display name from the Customers table
#   subject         str   ticket subject line
#   status          str   open | closed | in_progress | …
#   priority        str   low | medium | high | urgent
#   assigned_tech   str   technician email / name
#   problem_type    str   Syncro problem type category
#   last_synced_at  str   ISO-8601 timestamp of last sync

HUNTRESS_AGENTS_TABLE: dict[str, Any] = {
    "TableName": "HuntressAgents",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "agent_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "last_synced_at", "AttributeType": "S"},  # ISO-8601
        {"AttributeName": "status", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "agent_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All Huntress agents for a customer, sorted by sync time.
            "IndexName": "customer_id-last_synced_at-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "last_synced_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Agents filtered by status (online, offline, …) per customer.
            "IndexName": "customer_id-status-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "status", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Additional fields stored per item:
#   customer_name  str   display name from the Customers table
#   hostname       str   agent hostname
#   platform       str   windows | mac | linux
#   policy_name    str   Huntress policy applied to this agent
#   last_seen_at   str   ISO-8601 last heartbeat from the agent
#   version        str   Huntress agent version string

HUNTRESS_INCIDENTS_TABLE: dict[str, Any] = {
    "TableName": "HuntressIncidents",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "incident_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "created_at", "AttributeType": "S"},  # ISO-8601
        {"AttributeName": "severity", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "incident_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All Huntress incidents for a customer, sorted by creation time.
            "IndexName": "customer_id-created_at-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            # Incidents grouped by severity (critical, high, medium, low).
            "IndexName": "customer_id-severity-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "severity", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# Additional fields stored per item:
#   customer_name  str   display name from the Customers table
#   summary        str   short description of the incident
#   severity       str   critical | high | medium | low
#   status         str   open | closed | in_progress
#   type           str   Huntress incident type category
#   remediation    str   recommended remediation steps
#   created_at     str   ISO-8601 incident creation timestamp

SCOUTDNS_STATS_TABLE: dict[str, Any] = {
    "TableName": "ScoutDNSStats",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "stat_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "date", "AttributeType": "S"},  # YYYY-MM-DD
    ],
    "KeySchema": [
        {"AttributeName": "stat_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # Daily DNS stats for a customer, sorted by date.
            "IndexName": "customer_id-date-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "date", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# stat_id is a composite key: f"{customer_id}#{date}"
# Additional fields stored per item:
#   customer_name        str        display name from the Customers table
#   total_queries        int        total DNS queries for the day
#   blocked_queries      int        number of blocked queries
#   allowed_queries      int        number of allowed queries
#   top_blocked_domains  list[str]  top domains that were blocked
#   date                 str        YYYY-MM-DD

O365_LICENSES_TABLE: dict[str, Any] = {
    "TableName": "O365Licenses",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "license_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
    ],
    "KeySchema": [
        {"AttributeName": "license_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All license SKUs for a customer.
            "IndexName": "customer_id-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# license_id is a composite key: f"{customer_id}#{sku_id}"
# Additional fields stored per item:
#   customer_name    str   display name from the Customers table
#   sku_name         str   human-readable SKU name (e.g. "Microsoft 365 Business Premium")
#   total_units      int   total purchased licenses
#   consumed_units   int   currently assigned licenses
#   available_units  int   total_units - consumed_units
#   last_synced_at   str   ISO-8601 timestamp of last sync

O365_MAILBOXES_TABLE: dict[str, Any] = {
    "TableName": "O365Mailboxes",
    **_PAY_PER_REQUEST,
    "AttributeDefinitions": [
        {"AttributeName": "mailbox_id", "AttributeType": "S"},
        {"AttributeName": "customer_id", "AttributeType": "S"},
        {"AttributeName": "last_synced_at", "AttributeType": "S"},  # ISO-8601
    ],
    "KeySchema": [
        {"AttributeName": "mailbox_id", "KeyType": "HASH"},
    ],
    "GlobalSecondaryIndexes": [
        {
            # All mailboxes for a customer, sorted by sync time.
            "IndexName": "customer_id-last_synced_at-index",
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "last_synced_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        },
    ],
    "Tags": [{"Key": "Project", "Value": "msp-client-portal"}],
}
# mailbox_id is the user principal name (UPN / email address)
# Additional fields stored per item:
#   customer_name   str   display name from the Customers table
#   display_name    str   user display name
#   email           str   primary SMTP address
#   mailbox_type    str   UserMailbox | SharedMailbox | RoomMailbox | …
#   total_size_mb   int   mailbox quota in MB
#   used_size_mb    int   currently used storage in MB
#   item_count      int   total number of items in the mailbox
#   last_synced_at  str   ISO-8601 timestamp of last sync


# Ordered so dependencies come first (Tenants before child entities).
ALL_TABLES: list[dict[str, Any]] = [
    TENANTS_TABLE,
    TICKETS_TABLE,
    SECURITY_INCIDENTS_TABLE,
    DNS_EVENTS_TABLE,
    CUSTOMERS_TABLE,
    EC2_INSTANCES_TABLE,
    EC2_VOLUMES_TABLE,
    EC2_SNAPSHOTS_TABLE,
    SYNCRO_TICKETS_TABLE,
    HUNTRESS_AGENTS_TABLE,
    HUNTRESS_INCIDENTS_TABLE,
    SCOUTDNS_STATS_TABLE,
    O365_LICENSES_TABLE,
    O365_MAILBOXES_TABLE,
]


# ---------------------------------------------------------------------------
# Initialisation helper
# ---------------------------------------------------------------------------

def initialize_tables(
    region: str = "us-east-1",
    endpoint_url: str | None = None,
) -> dict[str, str]:
    """Create all MSP portal tables if they do not already exist.

    Parameters
    ----------
    region:
        AWS region to create tables in.
    endpoint_url:
        Override the DynamoDB endpoint — pass ``http://localhost:8000``
        when running against DynamoDB Local in development.

    Returns
    -------
    dict[str, str]
        Mapping of table name → outcome: ``"created"`` or ``"already_exists"``.
    """
    client = boto3.client(
        "dynamodb",
        region_name=region,
        **({"endpoint_url": endpoint_url} if endpoint_url else {}),
    )

    results: dict[str, str] = {}

    for table_def in ALL_TABLES:
        table_name: str = table_def["TableName"]
        try:
            client.create_table(**table_def)
            logger.info("Created table: %s", table_name)
            results[table_name] = "created"
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceInUseException":
                logger.debug("Table already exists: %s", table_name)
                results[table_name] = "already_exists"
            else:
                logger.error(
                    "Failed to create table %s: %s", table_name, exc
                )
                raise

    return results


def get_table_names() -> list[str]:
    """Return the canonical table names used by this application."""
    return [t["TableName"] for t in ALL_TABLES]

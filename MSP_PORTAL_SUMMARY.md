# MSP Client Portal — Project Summary for DynamoDB Integration Reference

This document summarizes the architecture, DynamoDB schema, and patterns used in the
Haley365 MSP Client Portal so that other projects can reuse or build on this foundation.

---

## Overview

A multi-tenant managed service provider (MSP) client portal at `portal.haley365.com`.
Allows MSP staff (admins) and end clients to view cloud resources, tickets, security
incidents, DNS activity, Office 365 data, and monitored devices in one place.

---

## Stack

| Layer    | Technology                                              |
|----------|---------------------------------------------------------|
| Frontend | Vite + React + React Router + Tailwind v3               |
| Backend  | FastAPI (Python), run via Mangum on AWS Lambda / EC2    |
| Database | AWS DynamoDB (multi-tenant, serverless, us-east-1)      |
| Auth     | JWT + magic link email (SMTP2GO)                        |
| Hosting  | EC2 (`/opt/msp-portal`) + nginx reverse proxy           |
| Deploy   | `./deploy.sh` on EC2                                    |

---

## AWS Credentials / IAM

The EC2 instance has an IAM role (`msp-portal-ec2-role`) with DynamoDB read/write access.
No AWS credentials are hardcoded anywhere. Boto3 picks up credentials automatically via
the instance metadata service.

```python
import boto3
ddb = boto3.resource('dynamodb', region_name='us-east-1')
tbl = ddb.Table('TableName')
```

Third-party API keys (Syncro, Huntress, ScoutDNS, CheckMK) are stored in
`/etc/msp-portal/sync.env` — never committed to git.

---

## DynamoDB Tables

### `Users`
Portal user accounts.

| Attribute    | Type   | Notes                        |
|--------------|--------|------------------------------|
| `user_id`    | String | PK (UUID)                    |
| `email`      | String | GSI: `email-index`           |
| `name`       | String |                              |
| `customer_id`| String | Tenant the user belongs to   |
| `is_admin`   | Bool   |                              |
| `is_active`  | Bool   |                              |
| `created_at` | String | ISO 8601                     |

**GSI:** `email-index` on `email` — used for login lookup.

---

### `Customers`
Tenant registry. Every other table is scoped by `customer_id`.

| Attribute     | Type   | Notes                                                      |
|---------------|--------|------------------------------------------------------------|
| `customer_id` | String | PK (e.g. `FPC`, `CENTRICITY-CA`, `BPRE`)                  |
| `name`        | String | Display name shown in UI                                   |
| `hidden`      | Bool   | If true, excluded from the customer dropdown               |
| `resolves_to` | String | Alias pointer — maps alternate names to canonical IDs      |

**Important pattern — alias records:** CheckMK uses group names that don't match portal
`customer_id` values. Rather than changing the data, alias records are written:
```python
# "Bickerstaff" in CheckMK maps to "BPRE" in the portal
tbl.put_item(Item={'customer_id': 'Bickerstaff', 'resolves_to': 'BPRE'})
```
The sync script resolves these at write time. The customer list API filters out alias
records (`not item.get('resolves_to')`) so they don't pollute the UI.

---

### `LoginAudit`
One record per login event.

| Attribute     | Type   | Notes         |
|---------------|--------|---------------|
| `user_id`     | String | PK            |
| `email`       | String |               |
| `logged_in_at`| String | ISO 8601, GSI |
| `ip`          | String |               |

---

### `SyncroTickets`
Support tickets synced from Syncro PSA.

| Attribute     | Type   | Notes                          |
|---------------|--------|--------------------------------|
| `ticket_id`   | String | PK                             |
| `customer_id` | String | GSI partition key              |
| `subject`     | String |                                |
| `status`      | String | e.g. `New`, `In Progress`, `Resolved` |
| `priority`    | String |                                |
| `created_at`  | String | ISO 8601                       |
| `updated_at`  | String | ISO 8601                       |

**GSIs:**
- `customer_id-created_at-index` — paginated ticket list sorted newest first
- `customer_id-status-index` — filter by specific status value

**Stale record cleanup pattern** (reusable):
```python
# Before sync: collect all existing IDs for this data source
existing = {item['ticket_id'] for item in tbl.scan(ProjectionExpression='ticket_id')['Items']}
# After sync: delete anything no longer in the source system
stale = existing - synced_ids
for tid in stale:
    tbl.delete_item(Key={'ticket_id': tid})
```

---

### `EC2Instances`, `EC2Volumes`, `EC2Snapshots`
AWS inventory.

| Attribute     | Type   | Notes              |
|---------------|--------|--------------------|
| `instance_id` | String | PK                 |
| `customer_id` | String | GSI partition key  |
| `name_tag`    | String | EC2 Name tag value |
| `state`       | String | running/stopped    |
| `region`      | String |                    |
| (+ more)      |        | type, tags, etc.   |

**GSI:** `customer_id-index` — list all resources for a tenant.

---

### `BackupJobs`
AWS Backup job history, synced across all AWS regions.

| Attribute         | Type   | Notes                                  |
|-------------------|--------|----------------------------------------|
| `job_id`          | String | PK                                     |
| `customer_id`     | String | GSI partition key                      |
| `vault_name`      | String |                                        |
| `resource_name`   | String | EC2 instance name                      |
| `resource_type`   | String | e.g. `EC2`                             |
| `state`           | String | `COMPLETED`, `FAILED`, etc.            |
| `region`          | String |                                        |
| `backup_size_bytes`| Number |                                       |
| `creation_date`   | String | ISO 8601, GSI sort key                 |
| `completion_date` | String | ISO 8601                               |

**GSI:** `customer_id-creation_date-index`

---

### `BackupCoverage`
Computed per-instance backup coverage status.

| Attribute       | Type   | Notes                              |
|-----------------|--------|------------------------------------|
| `instance_id`   | String | PK                                 |
| `customer_id`   | String | GSI partition key                  |
| `instance_name` | String |                                    |
| `region`        | String |                                    |
| `state`         | String | running/stopped                    |
| `backup_status` | String | `Protected` or `Not Backed Up`     |
| `last_backup_date` | String | ISO 8601                        |
| `gap_since`     | String | ISO 8601 — when gap was first seen |
| `checked_at`    | String | ISO 8601                           |

Coverage is computed by checking if any `BackupJob` with `state=COMPLETED` exists for
the instance within the last 14 days. Alert emails are sent on new gaps. Stale records
(terminated instances) are deleted each sync run.

---

### `HuntressAgents`
Endpoint security agents from Huntress EDR.

| Attribute     | Type   | Notes             |
|---------------|--------|-------------------|
| `agent_id`    | String | PK                |
| `customer_id` | String | GSI partition key |
| `hostname`    | String |                   |
| `status`      | String | online/offline    |
| (+ more)      |        |                   |

---

### `HuntressIncidents`
Security incidents from Huntress.

| Attribute     | Type   | Notes                            |
|---------------|--------|----------------------------------|
| `incident_id` | String | PK                               |
| `customer_id` | String | GSI partition key                |
| `summary`     | String |                                  |
| `severity`    | String | `low`, `high`, `critical`        |
| `status`      | String | `open`, `closed`, `in_progress`  |

---

### `CheckMKHosts`
Device monitoring hosts synced from CheckMK REST API every 10 minutes.

| Attribute        | Type     | Notes                                        |
|------------------|----------|----------------------------------------------|
| `host_name`      | String   | PK (CheckMK internal name)                   |
| `customer_id`    | String   | GSI partition key — resolved from host group |
| `alias`          | String   | Human-readable name (e.g. "Littleton (Nitel)") |
| `ip_address`     | String   |                                              |
| `status`         | String   | `Up`, `Down`, `Unreachable`, `Pending`       |
| `groups`         | List     | CheckMK host groups                          |
| `last_synced_at` | String   | ISO 8601, GSI sort key                       |

**GSI:** `customer_id-last_synced_at-index`

**Host group → customer_id resolution:**
```python
def _resolve_customer(groups: list[str], customers_tbl) -> str:
    for group in groups:
        resp = customers_tbl.get_item(Key={'customer_id': group})
        item = resp.get('Item')
        if item:
            return item.get('resolves_to') or item['customer_id']
    return 'unassigned'
```

**CheckMK API auth:**
```
Authorization: Bearer {CHECKMK_USERNAME} {CHECKMK_PASSWORD}
```
Base URL: `http://xg.checkmk.haley365.com/XG/`

State mapping: `{0: "Up", 1: "Down", 2: "Unreachable", -1: "Pending"}`

---

### `CheckMKServices`
Service-level monitoring per host.

| Attribute             | Type   | Notes                                |
|-----------------------|--------|--------------------------------------|
| `service_key`         | String | PK — `{host_name}#{service_description}` |
| `customer_id`         | String | GSI partition key                    |
| `host_name`           | String |                                      |
| `service_description` | String |                                      |
| `status`              | String | `Ok`, `Warn`, `Crit`, `Unknown`      |
| `plugin_output`       | String | Human-readable status message        |
| `last_synced_at`      | String | ISO 8601, GSI sort key               |

**GSI:** `customer_id-last_synced_at-index`

State mapping: `{0: "Ok", 1: "Warn", 2: "Crit", 3: "Unknown"}`

---

## Multi-Tenancy Pattern

This is the core architectural pattern used throughout the backend.

### JWT carries the customer_id
```python
# backend/app/core/dependencies.py
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    x_view_as_customer: str | None = Header(default=None),
) -> dict:
    payload = decode_access_token(credentials.credentials)
    customer_id = payload.get('sub')        # user's own tenant
    is_admin = payload.get('is_admin', False)

    effective_customer_id = customer_id
    if is_admin and x_view_as_customer:
        effective_customer_id = x_view_as_customer   # admin impersonation

    return {'customer_id': effective_customer_id, 'is_admin': is_admin, ...}
```

### Regular endpoints — scoped to one customer
```python
@router.get('/tickets')
def list_tickets(user: dict = Depends(get_current_user)) -> dict:
    customer_id = user['customer_id']   # already resolved (own or impersonated)
    tbl.query(
        IndexName='customer_id-created_at-index',
        KeyConditionExpression=Key('customer_id').eq(customer_id),
    )
```

### Admin global endpoints — full table scan
```python
@router.get('/admin/summary')
def admin_summary(user: dict = Depends(_require_admin)) -> dict:
    items = []
    kwargs = {}
    while True:
        resp = tbl.scan(**kwargs)
        items.extend(resp.get('Items', []))
        if not resp.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
    # filter out unassigned
    items = [i for i in items if i.get('customer_id') != 'unassigned']
```

### Frontend admin context switching
```typescript
// api.ts — automatically sends the header on every request
const viewAs = localStorage.getItem('viewAsCustomerId')
if (viewAs) config.headers['X-View-As-Customer'] = viewAs

// Component — use admin endpoints only when viewing own org (global view)
const viewingOwnOrg = !viewAsCustomerId || viewAsCustomerId === user?.customer_id
const useAdminEndpoints = user?.is_admin && viewingOwnOrg
const prefix = useAdminEndpoints ? '/monitoring/admin' : '/monitoring'
```

---

## Pagination Pattern (GSI-based)

DynamoDB doesn't support offset pagination. The portal uses cursor-based pagination
with base64-encoded `LastEvaluatedKey` tokens.

```python
import base64, json

def _encode_key(lek: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(lek).encode()).decode()

def _decode_key(token: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(token.encode()))

# In the endpoint:
kwargs = {
    'IndexName': 'customer_id-created_at-index',
    'KeyConditionExpression': Key('customer_id').eq(customer_id),
    'Limit': 50,
    'ScanIndexForward': False,   # newest first
}
if next_key:
    kwargs['ExclusiveStartKey'] = _decode_key(next_key)

resp = tbl.query(**kwargs)
return {
    'items': resp.get('Items', []),
    'next_key': _encode_key(resp['LastEvaluatedKey']) if resp.get('LastEvaluatedKey') else None,
    'count': resp.get('Count', 0),
}
```

---

## Sync Script Pattern

All sync scripts follow this structure:

```python
# backend/app/services/my_sync.py
import boto3, logging
from app.core.config import DYNAMODB_REGION

logger = logging.getLogger(__name__)

def lambda_handler(event=None, context=None):
    ddb = boto3.resource('dynamodb', region_name=DYNAMODB_REGION)
    tbl = ddb.Table('MyTable')

    # 1. Fetch data from external API
    items = fetch_from_api()

    # 2. Upsert to DynamoDB
    synced_ids = set()
    with tbl.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            synced_ids.add(item['id'])

    # 3. Delete stale records
    existing_ids = {i['id'] for i in tbl.scan(ProjectionExpression='id')['Items']}
    stale = existing_ids - synced_ids
    for sid in stale:
        tbl.delete_item(Key={'id': sid})

    logger.info(f'Sync complete: {len(synced_ids)} upserted, {len(stale)} deleted')
    return {'upserted': len(synced_ids), 'deleted': len(stale)}
```

Run via:
```bash
/opt/msp-portal/scripts/run_sync.sh app.services.my_sync
```

Cron entry:
```
*/10 * * * * /opt/msp-portal/scripts/run_sync.sh app.services.my_sync >> /var/log/msp-my-sync.log 2>&1
```

---

## Reserved Keywords in DynamoDB

Several common words are reserved and must use `ExpressionAttributeNames`:

```python
# 'name', 'status', 'hidden', 'state' are all reserved
tbl.update_item(
    Key={'customer_id': 'ACME'},
    UpdateExpression='SET #n = :n, #h = :h',
    ExpressionAttributeNames={'#n': 'name', '#h': 'hidden'},
    ExpressionAttributeValues={':n': 'Acme Corp', ':h': True},
)
```

When in doubt, wrap every attribute name in `ExpressionAttributeNames`.

---

## One-off DynamoDB Operations (no AWS CLI)

The EC2 server doesn't have the AWS CLI installed. Use boto3 directly:

```bash
python3 - <<'EOF'
import boto3
ddb = boto3.resource('dynamodb', region_name='us-east-1')
tbl = ddb.Table('Customers')
tbl.update_item(
    Key={'customer_id': 'ACME'},
    UpdateExpression='SET #n = :n',
    ExpressionAttributeNames={'#n': 'name'},
    ExpressionAttributeValues={':n': 'Acme Corp'},
)
print('Done')
EOF
```

---

## Repository

**GitHub:** `jhaley365/msp-client-portal`
**Active branch:** `claude/practical-sagan-kkwh99`
**Production path on EC2:** `/opt/msp-portal`

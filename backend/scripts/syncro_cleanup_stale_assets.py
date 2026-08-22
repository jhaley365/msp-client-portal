"""
Syncro — Delete Stale FPC Assets
=================================
Finds Syncro assets for the FPC customer that have not been updated in
more than STALE_DAYS days and optionally deletes them.

Run in DRY-RUN mode first (default) to review what would be deleted:
    ../.venv/bin/python scripts/syncro_cleanup_stale_assets.py

Then run with --delete to actually remove them:
    ../.venv/bin/python scripts/syncro_cleanup_stale_assets.py --delete

Options:
    --delete        Actually delete (default is dry-run only)
    --days N        Stale threshold in days (default: 60)
    --customer NAME Syncro customer name filter (default: FPC)
"""

from __future__ import annotations

import os
import sys
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_STALE_DAYS  = 60
DEFAULT_CUSTOMER    = "FPC"

SYNCRO_API_KEY   = os.environ.get("SYNCRO_API_KEY", "")
SYNCRO_SUBDOMAIN = os.environ.get("SYNCRO_SUBDOMAIN", "haley365")

if not SYNCRO_API_KEY:
    env_file = "/etc/msp-portal/sync.env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SYNCRO_API_KEY="):
                    SYNCRO_API_KEY = line.split("=", 1)[1]
                if line.startswith("SYNCRO_SUBDOMAIN="):
                    SYNCRO_SUBDOMAIN = line.split("=", 1)[1]

SYNCRO_BASE = f"https://{SYNCRO_SUBDOMAIN}.syncromsp.com/api/v1"

HEADERS = {
    "Authorization": SYNCRO_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_all_assets(customer_filter: str) -> list[dict]:
    """Fetch all assets, optionally filtered by customer name."""
    assets: list[dict] = []
    page = 1
    while True:
        params: dict = {"page": page, "per_page": 100}
        resp = requests.get(f"{SYNCRO_BASE}/customer_assets",
                            headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"ERROR fetching assets (page {page}): {resp.status_code} {resp.text[:200]}")
            sys.exit(1)
        data = resp.json()
        batch = data.get("assets", [])
        if not batch:
            break
        assets.extend(batch)
        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        print(f"  Fetched page {page}/{total_pages} ({len(assets)} assets so far)")
        if page >= total_pages:
            break
        page += 1

    if customer_filter:
        before = len(assets)
        assets = [
            a for a in assets
            if customer_filter.upper() in (
                (a.get("customer") or {}).get("business_name") or ""
            ).upper()
        ]
        print(f"  Filtered to '{customer_filter}' customer: {len(assets)} of {before} assets")

    return assets


def parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    s = date_str.strip()
    # Normalise -HH:MM offset to +HHMM so %z can parse it
    import re
    s = re.sub(r'([+-])(\d{2}):(\d{2})$', r'\1\2\3', s)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def find_stale(assets: list[dict], stale_days: int) -> list[dict]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=stale_days)
    stale = []
    for a in assets:
        rmm = a.get("rmm_store") or {}
        last_updated = (
            parse_date(rmm.get("updated_at")) or      # RMM agent last sync (matches Syncro UI)
            parse_date(a.get("updated_at")) or
            parse_date(a.get("created_at"))
        )
        if last_updated and last_updated < cutoff:
            a["_last_updated"] = last_updated
            stale.append(a)
    return stale


def delete_asset(asset_id: int) -> bool:
    resp = requests.delete(f"{SYNCRO_BASE}/customer_assets/{asset_id}",
                           headers=HEADERS, timeout=30)
    return resp.status_code in (200, 204)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete",   action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--days",     type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--customer", default=DEFAULT_CUSTOMER)
    args = parser.parse_args()

    if not SYNCRO_API_KEY:
        print("ERROR: SYNCRO_API_KEY not found.")
        sys.exit(1)

    mode = "DELETE" if args.delete else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"  Syncro Stale Asset Cleanup — {mode}")
    print(f"  Customer : {args.customer}")
    print(f"  Threshold: {args.days} days")
    print(f"  Cutoff   : {(datetime.now(tz=timezone.utc) - timedelta(days=args.days)).strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    print("Fetching assets from Syncro...")
    all_assets = fetch_all_assets(args.customer)

    stale = find_stale(all_assets, args.days)
    stale.sort(key=lambda a: a["_last_updated"])

    if not stale:
        print(f"\nNo stale assets found (>{args.days} days since last update).")
        return

    print(f"\nFound {len(stale)} stale assets (not updated in >{args.days} days):\n")
    print(f"  {'ID':<10} {'Last Updated':<14} {'Name':<35} {'OS':<30} {'Customer'}")
    print(f"  {'-'*9} {'-'*13} {'-'*34} {'-'*29} {'-'*20}")
    for a in stale:
        last = a["_last_updated"].strftime("%Y-%m-%d")
        name = (a.get("name") or a.get("hostname") or "")[:34]
        os_  = (a.get("os_version") or a.get("operating_system") or a.get("os") or "")[:29]
        cust = ((a.get("customer") or {}).get("business_name") or "")[:20]
        print(f"  {a['id']:<10} {last:<14} {name:<35} {os_:<30} {cust}")

    print(f"\nTotal: {len(stale)} assets would be {'DELETED' if args.delete else 'deleted (dry-run)'}.")

    if not args.delete:
        print("\n*** DRY-RUN — nothing was deleted. ***")
        print("    Run with --delete to permanently remove these assets.")
        return

    # ── Confirm before deleting ───────────────────────────────────────────────
    confirm = input(f"\nType 'yes' to permanently delete {len(stale)} assets: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    print("\nDeleting...")
    deleted = 0
    failed  = 0
    for a in stale:
        name = (a.get("name") or a.get("hostname") or str(a["id"]))
        if delete_asset(a["id"]):
            print(f"  ✓ Deleted {a['id']} — {name}")
            deleted += 1
        else:
            print(f"  ✗ Failed  {a['id']} — {name}")
            failed += 1
        time.sleep(0.2)   # gentle rate limiting

    print(f"\nDone. Deleted: {deleted}  Failed: {failed}")


if __name__ == "__main__":
    main()

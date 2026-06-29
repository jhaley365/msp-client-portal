"""
List all Syncro customers so you can identify their numeric IDs.

Run from the repo root:
    SYNCRO_API_KEY=<key> SYNCRO_SUBDOMAIN=haley365 \
        PYTHONPATH=./backend python backend/scripts/syncro_list_customers.py
"""

import os
import requests

API_KEY = os.environ["SYNCRO_API_KEY"]
SUBDOMAIN = os.environ["SYNCRO_SUBDOMAIN"]
BASE = f"https://{SUBDOMAIN}.syncromsp.com/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}


def list_customers() -> None:
    page = 1
    total = 0
    while True:
        resp = requests.get(f"{BASE}/customers", headers=HEADERS, params={"page": page}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        customers = data.get("customers", [])
        if not customers:
            break
        for c in customers:
            name = c.get("business_name") or f"{c.get('firstname', '')} {c.get('lastname', '')}".strip()
            print(f"  ID: {c['id']:<10}  Name: {name}")
            total += 1
        meta = data.get("meta", {})
        if page >= (meta.get("total_pages") or 1):
            break
        page += 1
    print(f"\nTotal: {total} customers")


if __name__ == "__main__":
    print(f"Fetching customers from {BASE}\n")
    list_customers()

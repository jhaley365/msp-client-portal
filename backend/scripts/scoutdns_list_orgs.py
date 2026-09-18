"""
List ScoutDNS organizations with their IDs.

Usage (from repo root on EC2):
    set -a; source /etc/msp-portal/sync.env; set +a
    PYTHONPATH=backend python backend/scripts/scoutdns_list_orgs.py
"""

from __future__ import annotations

import os
import requests

API_KEY = os.environ.get("SCOUTDNS_API_KEY", "")
BASE_URL = "https://api.scoutdns.com/app"

sess = requests.Session()
sess.headers.update({"X-API-ACCESS-KEY": API_KEY, "Accept": "application/json"})

resp = sess.get(f"{BASE_URL}/getOrganizations", timeout=30)
resp.raise_for_status()
orgs = resp.json().get("data", [])

print(f"{'ID':<40} {'Name'}")
print("-" * 70)
for org in orgs:
    print(f"{org.get('id', ''):<40} {org.get('name', '')}")

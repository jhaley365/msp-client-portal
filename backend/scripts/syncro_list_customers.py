"""Quick diagnostic — list unique customer_name values in Syncro assets."""
from __future__ import annotations
import os, sys, requests
from collections import Counter

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

if not SYNCRO_API_KEY:
    print("ERROR: SYNCRO_API_KEY not found")
    sys.exit(1)

BASE = f"https://{SYNCRO_SUBDOMAIN}.syncromsp.com/api/v1"
HEADERS = {"Authorization": SYNCRO_API_KEY, "Accept": "application/json"}

assets, page = [], 1
while True:
    resp = requests.get(f"{BASE}/customer_assets", headers=HEADERS,
                        params={"page": page, "per_page": 100}, timeout=30)
    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)
    data = resp.json()
    batch = data.get("assets", [])
    if not batch:
        break
    assets.extend(batch)
    total_pages = data.get("meta", {}).get("total_pages", 1)
    print(f"  page {page}/{total_pages}  ({len(assets)} assets)", flush=True)
    if page >= total_pages:
        break
    page += 1

print(f"\nTotal assets: {len(assets)}\n")

# Show all keys in the first asset
if assets:
    print("Keys in first asset record:")
    for k, v in assets[0].items():
        print(f"  {k!r:35s} = {str(v)[:80]!r}")

print("\nUnique customer_name values (count):")
counts = Counter(str(a.get("customer_name") or "") for a in assets)
for name, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {cnt:5d}  {name!r}")

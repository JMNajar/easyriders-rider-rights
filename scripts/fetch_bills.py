#!/usr/bin/env python3
"""
Fetches federal bill status from Congress.gov API and updates data/bills.json.
Preserves existing bill data and updates status/cosponsor counts.
"""

import json
import os
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

CONGRESS_API_KEY = os.environ.get("CONGRESS_API_KEY", "")
OUTPUT_FILE = "data/bills.json"

# Bill IDs to track: (congress, type, number)
TRACKED_BILLS = [
    (119, "hr", 906),    # REPAIR Act
    (119, "s", 1424),    # Stop Motorcycle Profiling Act (Senate)
    (119, "hr", 2843),   # Stop Motorcycle Profiling Act (House)
]


def fetch_bill(congress, bill_type, number):
    if not CONGRESS_API_KEY:
        print("No CONGRESS_API_KEY set — skipping live fetch.")
        return None
    url = f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{number}?api_key={CONGRESS_API_KEY}&format=json"
    try:
        req = Request(url, headers={"User-Agent": "EasyridersPolicyTracker/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("bill", {})
    except (URLError, json.JSONDecodeError) as e:
        print(f"Congress API error for {bill_type}{number}: {e}")
        return None


def fetch_cosponsor_count(congress, bill_type, number):
    if not CONGRESS_API_KEY:
        return None
    url = f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{number}/cosponsors?api_key={CONGRESS_API_KEY}&format=json"
    try:
        req = Request(url, headers={"User-Agent": "EasyridersPolicyTracker/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("pagination", {}).get("count", 0)
    except Exception:
        return None


def map_status(actions):
    if not actions:
        return "Introduced"
    latest = actions[0].get("type", "") if actions else ""
    text = actions[0].get("text", "") if actions else ""
    if "became law" in text.lower() or "signed by president" in text.lower():
        return "Signed into Law"
    if "passed" in text.lower() and "house" in text.lower():
        return "Passed House"
    if "passed" in text.lower() and "senate" in text.lower():
        return "Passed Senate"
    if "committee" in text.lower():
        return "In Committee"
    return "Introduced"


def main():
    if not os.path.exists(OUTPUT_FILE):
        print(f"{OUTPUT_FILE} not found — cannot update.")
        return

    with open(OUTPUT_FILE) as f:
        data = json.load(f)

    updated_count = 0
    for congress, bill_type, number in TRACKED_BILLS:
        bill_id = f"{bill_type.upper()}{number}"
        bill_data = fetch_bill(congress, bill_type, number)
        if not bill_data:
            continue

        cosponsor_count = fetch_cosponsor_count(congress, bill_type, number)

        for bill in data["bills"]:
            if bill["id"] == bill_id:
                actions = bill_data.get("actions", {}).get("item", [])
                new_status = map_status(actions)
                if bill["status"] != new_status:
                    print(f"{bill_id}: {bill['status']} → {new_status}")
                    bill["status"] = new_status

                if cosponsor_count is not None:
                    bill["cosponsors"] = cosponsor_count

                updated_count += 1
                break

    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {updated_count} federal bills. Written to {OUTPUT_FILE}.")


if __name__ == "__main__":
    main()

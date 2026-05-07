#!/usr/bin/env python3
"""
Reads bills.json and derives updated signal card status for the dashboard.
Updates data/status.json week_in_review and last_updated timestamp.
"""

import json
import os
from datetime import datetime, timezone

BILLS_FILE = "data/bills.json"
STATUS_FILE = "data/status.json"


def momentum_to_dot(momentum):
    mapping = {"ACTIVE": "active", "MOVING": "moving", "QUIET": "quiet", "WATCH": "watch", "ONGOING": "active"}
    return mapping.get(momentum.upper(), "quiet")


def main():
    if not os.path.exists(STATUS_FILE):
        print(f"{STATUS_FILE} not found.")
        return

    with open(STATUS_FILE) as f:
        status_data = json.load(f)

    if os.path.exists(BILLS_FILE):
        with open(BILLS_FILE) as f:
            bills_data = json.load(f)

        # Find federal bills and update signal that references them
        for bill in bills_data.get("bills", []):
            if bill["id"] == "HR906":
                cospon = bill.get("cosponsors", 67)
                for sig in status_data["signals"]:
                    if sig["id"] == "repair-act":
                        sig["detail"] = (
                            f"H.R. 906 — {cospon} cosponsors. "
                            f"Status: {bill.get('status', 'In Committee')}. "
                            "Manufacturer lobbying remains the primary obstacle."
                        )
                        break

    status_data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(STATUS_FILE, "w") as f:
        json.dump(status_data, f, indent=2)

    print(f"Status updated. Written to {STATUS_FILE}.")


if __name__ == "__main__":
    main()

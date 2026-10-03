#!/usr/bin/env python3
"""Small production synthetic suite for CarScanner's customer-facing API.

This intentionally tests a handful of representative journeys against the
deployed service. It does not assert that every source has inventory today:
marketplace inventory is inherently time-varying. It does assert the API
contract, condition isolation, budget filtering, source-plan coverage and
India-wide destination semantics.
"""
import json
import os
import sys
import urllib.request

BASE = os.getenv("CARSCANNER_BASE_URL", "https://buy-premium-car1.onrender.com").rstrip("/")

JOURNEYS = [
    {"name": "Mercedes E-Class used", "query": "Mercedes-Benz Mercedes-Benz E-Class", "condition": "used"},
    {"name": "Mercedes E-Class demo", "query": "Mercedes-Benz Mercedes-Benz E-Class", "condition": "demo"},
    {"name": "BMW 3 Series used", "query": "BMW BMW 3 Series", "condition": "used"},
    {"name": "BMW X5 demo", "query": "BMW BMW X5", "condition": "demo"},
    {"name": "Audi Q5 used", "query": "Audi Audi Q5", "condition": "used"},
]

def post(body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + "/api/search",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        assert response.status == 200, response.status
        return json.load(response)

def main():
    failures = []
    for journey in JOURNEYS:
        for destination in ("Bengaluru", None):
            body = dict(journey, destination=destination)
            try:
                payload = post(body)
                assert payload.get("ok") is True
                assert payload.get("search_scope") == "india"
                assert isinstance(payload.get("sources"), list)
                assert isinstance(payload.get("source_plan"), list)

                if journey["condition"] == "demo":
                    # The plan must include the dedicated demo sources for the
                    # two demo journeys where those adapters are registered.
                    names = {str(x.get("name")) for x in payload["source_plan"]}
                    if "Mercedes" in journey["query"]:
                        assert "Mercedes-Benz Used Cars" in names
                    if "BMW" in journey["query"]:
                        assert "Motozite Demo" in names

                for row in payload.get("results", []):
                    if journey["condition"] in ("used", "demo"):
                        actual = str(row.get("condition_signal") or "").lower()
                        if actual:
                            assert actual == journey["condition"], row

                print("PASS", journey["name"], "destination=", destination,
                      "mode=", payload.get("mode"),
                      "results=", payload.get("total_results"))
            except Exception as exc:
                failures.append((journey["name"], destination, repr(exc)))

    if failures:
        print("\nFAILURES:")
        for item in failures:
            print(item)
        return 1
    print("\nAll production synthetic journeys passed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

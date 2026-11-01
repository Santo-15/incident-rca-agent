# Run the whole agent once: alerts from the live Alertmanager (default) or from a saved webhook JSON file.
# Usage: python -m agent.run   |   python -m agent.run --payload path/to/alerts.json
import argparse
import json
import logging
import os
import time
import httpx
from agent.graph import build_graph

AM_URL = os.getenv("ALERTMANAGER_URL", "http://127.0.0.1:9093")


def live_payload() -> dict:
    resp = httpx.get(f"{AM_URL}/api/v2/alerts", params={"active": "true", "silenced": "false", "inhibited": "false"}, timeout=10)
    resp.raise_for_status()
    return {"alerts": resp.json()}   # same shape as the webhook's "alerts" list; triage reads both status formats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", help="Alertmanager webhook JSON file (default: live alerts)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    payload = json.load(open(args.payload)) if args.payload else live_payload()

    start = time.perf_counter()
    out = build_graph().invoke({"payload": payload})
    print(out["report"])
    print(f"\ntime to diagnosis: {time.perf_counter() - start:.1f} s · findings: {len(out.get('findings', []))}")   # KEY: success criterion < 5 min
    print("memory hits:", [(h["scenario"], h["distance"]) for h in out.get("similar", [])] or "none")


if __name__ == "__main__":
    main()

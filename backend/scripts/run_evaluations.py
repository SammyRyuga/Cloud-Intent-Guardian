#!/usr/bin/env python3
"""Run queued fixture evaluations against DynamoDB Local only."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", help="Run one queued evaluation ID; defaults to a bounded queued-job batch.")
    parser.add_argument("--reconcile", action="store_true", help="Fail only expired/exhausted jobs instead of running queued jobs.")
    args = parser.parse_args()
    local = os.environ.get("CIG_LOCAL", "").lower() == "true" or os.environ.get("AWS_SAM_LOCAL", "").lower() == "true"
    if not local:
        parser.error("This runner is restricted to explicit CIG_LOCAL=true or AWS_SAM_LOCAL=true mode.")
    if os.environ.get("INVENTORY_PROVIDER") != "fixture":
        parser.error("Set INVENTORY_PROVIDER=fixture; this runner never invokes live cloud discovery.")
    if not os.environ.get("DYNAMODB_ENDPOINT_URL"):
        parser.error("Set DYNAMODB_ENDPOINT_URL to the local DynamoDB endpoint.")

    from common.dynamodb import dynamodb_resource
    from common.contracts import scan_all
    from evaluation_worker.app import lambda_handler, reconcile_expired

    db = dynamodb_resource()
    if args.reconcile:
        results = reconcile_expired(db, args.id)
        for result in results:
            print(f"{result['evaluationId']} {result['result']}")
        if not results:
            print("No expired evaluation jobs required reconciliation.")
        return 0

    table = db.Table(os.environ["EVALUATIONS_TABLE"])
    if args.id:
        ids = [args.id]
    else:
        rows, truncated = scan_all(table, max_pages=4)
        if truncated:
            parser.error("Queued-job scan exceeded its safety bound; specify --id.")
        ids = [row["evaluationId"] for row in rows if row.get("status") == "QUEUED"][:25]
    for evaluation_id in ids:
        result = lambda_handler({"evaluationId": evaluation_id}, None)["results"][0]
        print(f"{evaluation_id} {result['result']}")
    if not ids:
        print("No queued evaluations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

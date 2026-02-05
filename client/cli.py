import argparse
import json
import sys
from pathlib import Path

import requests

API_BASE_URL = "http://127.0.0.1:8000"


# -----------------------------
# Helpers
# -----------------------------

def load_payload(file_path: str) -> dict:
    path = Path(file_path)

    if not path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"❌ Invalid JSON: {exc}")
        sys.exit(1)


def submit_job(payload: dict) -> None:
    url = f"{API_BASE_URL}/build"

    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as exc:
        print(f"❌ Failed to connect to API: {exc}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"❌ API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    data = response.json()

    print("\n✅ Job submitted successfully")
    print(f"Job ID : {data.get('job_id')}")
    print(f"Status : {data.get('status')}")
    print("")


# -----------------------------
# CLI entrypoint
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AutoDev AI CLI"
    )

    subparsers = parser.add_subparsers(dest="command")

    # submit command
    submit_parser = subparsers.add_parser(
        "submit",
        help="Submit a new AutoDev job"
    )
    submit_parser.add_argument(
        "file",
        help="Path to JSON file describing the project"
    )

    args = parser.parse_args()

    if args.command == "submit":
        payload = load_payload(args.file)
        submit_job(payload)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""
Collect one snapshot of live wait times for the four Walt Disney World parks
from the Queue-Times.com API (Powered by Queue-Times.com) and append it to
today's CSV in data/raw/.

Runs every 30 minutes on GitHub Actions. Standard library only, so the
collector has no dependencies to break.

    python scripts/collect.py                          # live API
    python scripts/collect.py --fixtures tests/fixtures  # offline, for tests
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
API = "https://queue-times.com/parks/{park_id}/queue_times.json"
PARKS = {
    6: "Magic Kingdom",
    5: "EPCOT",
    7: "Hollywood Studios",
    8: "Animal Kingdom",
}
FIELDS = [
    "collected_at", "park_id", "park_name", "land_name", "ride_id", "ride_name",
    "is_open", "wait_time", "last_updated",
]


def fetch(park_id: int, retries: int = 3) -> dict:
    url = API.format(park_id=park_id)
    req = urllib.request.Request(url, headers={"User-Agent": "disney-world-wait-times (github.com/jsalerno12345)"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except Exception as exc:  # network blips are normal; retry with backoff
            if attempt == retries:
                raise
            print(f"park {park_id}: attempt {attempt} failed ({exc}); retrying", file=sys.stderr)
            time.sleep(5 * attempt)
    raise RuntimeError("unreachable")


def flatten(payload: dict, park_id: int, collected_at: str) -> list[dict]:
    """The API nests rides inside lands, plus a top-level list for rides with no land."""
    groups = [(land["name"], land["rides"]) for land in payload.get("lands", [])]
    groups.append(("", payload.get("rides", [])))
    rows = []
    for land_name, rides in groups:
        for ride in rides:
            rows.append({
                "collected_at": collected_at,
                "park_id": park_id,
                "park_name": PARKS[park_id],
                "land_name": land_name,
                "ride_id": ride["id"],
                "ride_name": ride["name"],
                "is_open": int(bool(ride["is_open"])),
                "wait_time": int(ride["wait_time"] or 0),
                "last_updated": ride["last_updated"],
            })
    return rows


def validate(rows: list[dict]) -> None:
    """Fail loudly instead of committing garbage."""
    if not rows:
        raise SystemExit("No rides returned by the API; refusing to write an empty snapshot.")
    for r in rows:
        if not 0 <= r["wait_time"] <= 600:
            raise SystemExit(f"Implausible wait time {r['wait_time']} for {r['ride_name']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, help="read park_<id>.json files instead of calling the API")
    parser.add_argument("--raw-dir", type=Path, default=RAW, help="where snapshot CSVs go")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    collected_at = now.isoformat().replace("+00:00", "Z")
    rows: list[dict] = []
    for park_id in PARKS:
        if args.fixtures:
            path = args.fixtures / f"park_{park_id}.json"
            if not path.exists():
                continue
            payload = json.loads(path.read_text())
        else:
            payload = fetch(park_id)
        rows.extend(flatten(payload, park_id, collected_at))
    validate(rows)

    out = args.raw_dir / now.strftime("%Y") / now.strftime("%m") / f"{now:%Y-%m-%d}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
    open_rides = sum(r["is_open"] for r in rows)
    print(f"{collected_at}: {len(rows)} attractions ({open_rides} open) -> {out}")


if __name__ == "__main__":
    main()

"""
Write a week of realistic-looking FAKE snapshots for testing the build and
dashboard locally or in CI. Never committed to data/raw.

    python tests/make_fake_history.py /tmp/fake_raw --days 7
"""

import argparse
import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

RIDES = [  # (park_id, park, land, ride_id, name, peak wait)
    (6, "Magic Kingdom", "Tomorrowland", 11527, "TRON Lightcycle / Run", 90),
    (6, "Magic Kingdom", "Fantasyland", 129, "Seven Dwarfs Mine Train", 75),
    (6, "Magic Kingdom", "Fantasyland", 136, "Peter Pan's Flight", 55),
    (6, "Magic Kingdom", "Fantasyland", 13763, "Cinderella Castle", 0),
    (5, "EPCOT", "World Discovery", 10093, "Guardians of the Galaxy: Cosmic Rewind", 95),
    (5, "EPCOT", "World Discovery", 160, "Test Track", 70),
    (5, "EPCOT", "World Showcase", 8956, "Remy's Ratatouille Adventure", 60),
    (7, "Hollywood Studios", "Galaxy's Edge", 6368, "Star Wars: Rise of the Resistance", 100),
    (7, "Hollywood Studios", "Toy Story Land", 6361, "Slinky Dog Dash", 80),
    (8, "Animal Kingdom", "Pandora", 4439, "Avatar Flight of Passage", 85),
    (8, "Animal Kingdom", "Africa", 128, "Kilimanjaro Safaris", 40),
]
FIELDS = ["collected_at", "park_id", "park_name", "land_name", "ride_id", "ride_name",
          "is_open", "wait_time", "last_updated"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out", type=Path)
    p.add_argument("--days", type=int, default=7)
    a = p.parse_args()
    rng = random.Random(1)
    start = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)  # 8am Eastern
    for d in range(a.days):
        day0 = start + timedelta(days=d)
        rows = []
        for k in range(31):  # every 30 min, 8am to 11pm Eastern
            t = day0 + timedelta(minutes=30 * k)
            local_hour = 8 + k / 2
            shape = max(0.15, math.sin(math.pi * (local_hour - 8) / 14))  # peaks early afternoon
            weekend = 1.25 if t.weekday() >= 5 else 1.0
            for park_id, park, land, rid, name, peak in RIDES:
                is_open = int(rng.random() > 0.05)
                wait = 0 if (peak == 0 or not is_open) else max(5, int(round(peak * shape * weekend * rng.uniform(0.8, 1.2) / 5) * 5))
                ts = t.isoformat().replace("+00:00", "Z")
                rows.append(dict(collected_at=ts, park_id=park_id, park_name=park, land_name=land, ride_id=rid,
                                 ride_name=name, is_open=is_open, wait_time=wait, last_updated=ts))
        f = a.out / f"{day0:%Y}" / f"{day0:%m}" / f"{day0:%Y-%m-%d}.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"Wrote {a.days} days of fake snapshots to {a.out}")


if __name__ == "__main__":
    main()

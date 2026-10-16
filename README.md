# Walt Disney World wait times

[![Collect wait times](https://github.com/jsalerno12345/disney-world-wait-times/actions/workflows/collect.yml/badge.svg)](https://github.com/jsalerno12345/disney-world-wait-times/actions/workflows/collect.yml)
[![Tests](https://github.com/jsalerno12345/disney-world-wait-times/actions/workflows/test.yml/badge.svg)](https://github.com/jsalerno12345/disney-world-wait-times/actions/workflows/test.yml)

**[Live dashboard](https://jsalerno12345.github.io/disney-world-wait-times/)** · Powered by [Queue-Times.com](https://queue-times.com/)

A self-updating data pipeline that records posted wait times for every attraction at Magic Kingdom, EPCOT, Hollywood Studios and Animal Kingdom every 30 minutes, and answers the question every park-goer asks: **when is the best time to ride?**

## How it works

```
GitHub Actions (every 30 min)
  │
  ├─ scripts/collect.py    Queue-Times API → 4 parks → flat rows → data/raw/YYYY/MM/YYYY-MM-DD.csv
  │                        (standard library only; retries; refuses empty or implausible data)
  ├─ scripts/build.py      DuckDB SQL over every snapshot → reports/summary.json
  │                        local-time conversion, queued-attraction filter, hourly averages, best/worst hour
  ├─ index.html            static dashboard rendered from the summary, served by GitHub Pages
  └─ git commit + push     the repo *is* the database ("git scraping")
```

No servers, no database, no cost. The history lives in plain CSV files anyone can download.

## What the dashboard shows

- **Right now:** longest current waits and the busiest park.
- **By time of day:** average wait per park for each hour, in park time.
- **Best time to ride:** per attraction, the hour with the lowest average wait between 9am and 9pm, plus the worst hour.
- **Longest average waits** across all snapshots.

## Definitions

- Waits are **posted** waits as published by the parks, not measured actual waits.
- Times are converted from UTC to **America/New_York**.
- **Queued attractions** are those that have ever posted a wait above 0. Shows and walk-throughs that always post 0 are excluded from averages so they don't drag them down.
- Averages use only snapshots where the attraction was **open**.
- "Best hour" requires at least 3 snapshots in that hour, so it fills in as data accumulates.

## Data dictionary (`data/raw/**.csv`)

| Column | Meaning |
|---|---|
| `collected_at` | When this snapshot was taken (UTC) |
| `park_id`, `park_name` | Queue-Times park ID and name |
| `land_name` | Themed land (blank if the API lists the attraction without one) |
| `ride_id`, `ride_name` | Queue-Times attraction ID and name |
| `is_open` | 1 if operating at snapshot time |
| `wait_time` | Posted wait in minutes |
| `last_updated` | When Queue-Times last refreshed this attraction (UTC) |

## Tests

On every code push, GitHub Actions checks that the collector parses saved real API responses (`tests/fixtures/`) and that the build produces a sane summary from a week of generated test data (`tests/make_fake_history.py`). Neither touches the network or the real data.

## Run locally

```bash
pip install -r requirements.txt
python scripts/collect.py    # one snapshot
python scripts/build.py      # rebuild index.html
```

## Notes

- GitHub's scheduler can delay runs by several minutes at busy times, so snapshots are roughly, not exactly, 30 minutes apart.
- Data begins in October 2026; patterns get more reliable as weeks accumulate.

## Attribution

Wait time data is **Powered by [Queue-Times.com](https://queue-times.com/)**, used under their free API terms.
This is an independent hobby project and is not affiliated with or endorsed by The Walt Disney Company.

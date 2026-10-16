"""
Turn every collected snapshot into summary tables, then render the dashboard.

    data/raw/**/*.csv  ->  DuckDB SQL  ->  reports/summary.json  ->  index.html

Definitions
- Times are converted to park local time (America/New_York).
- "Queued attractions" are ones that have ever posted a wait above 0.
  Shows, walk-throughs and meet-and-greet spots that always post 0 are left out
  of averages so they don't drag them down.
- Averages only use snapshots where the attraction was open.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
TZ = "America/New_York"
MIN_OBS_PER_HOUR = 3


def q(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    out = []
    for row in cur.fetchall():
        out.append({c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, row)})
    return out


def build(raw: Path) -> dict:
    con = duckdb.connect()
    files = sorted(raw.rglob("*.csv"))
    if not files:
        raise SystemExit(f"No snapshot files under {raw}")
    con.execute(f"""
        create view snapshots as
        select
            *,
            timezone('{TZ}', cast(collected_at as timestamptz)) as local_ts
        from read_csv({[str(f) for f in files]}, header = true,
                      columns = {{
                        'collected_at': 'VARCHAR', 'park_id': 'INTEGER', 'park_name': 'VARCHAR',
                        'land_name': 'VARCHAR', 'ride_id': 'INTEGER', 'ride_name': 'VARCHAR',
                        'is_open': 'INTEGER', 'wait_time': 'INTEGER', 'last_updated': 'VARCHAR'}})
    """)
    con.execute("""
        create view queued as
        select s.*, hour(local_ts) as local_hour, dayname(local_ts) as local_weekday,
               isodow(local_ts) as weekday_num, cast(local_ts as date) as local_date
        from snapshots s
        where is_open = 1
          and ride_id in (select ride_id from snapshots group by ride_id having max(wait_time) > 0)
    """)

    meta = q(con, """
        select count(distinct collected_at) as snapshots,
               count(distinct ride_id) as attractions_seen,
               (select count(distinct ride_id) from queued) as queued_attractions,
               min(local_ts) as first_local, max(local_ts) as last_local,
               count(distinct cast(local_ts as date)) as days
        from snapshots
    """)[0]

    latest = q(con, """
        select park_name, ride_name, land_name, wait_time
        from queued
        where collected_at = (select max(collected_at) from snapshots)
        order by wait_time desc
    """)

    park_now = q(con, """
        select park_name, round(avg(wait_time), 1) as avg_wait, max(wait_time) as max_wait, count(*) as open_queued
        from queued
        where collected_at = (select max(collected_at) from snapshots)
        group by park_name order by avg_wait desc
    """)

    by_hour = q(con, """
        select park_name, local_hour, round(avg(wait_time), 1) as avg_wait, count(*) as obs
        from queued
        group by park_name, local_hour
        order by park_name, local_hour
    """)

    by_weekday = q(con, """
        select park_name, weekday_num, local_weekday, round(avg(wait_time), 1) as avg_wait,
               count(distinct local_date) as days
        from queued
        group by all order by park_name, weekday_num
    """)

    rides = q(con, f"""
        with hourly as (
            select ride_id, local_hour, avg(wait_time) as avg_wait, count(*) as obs
            from queued where local_hour between 9 and 21
            group by ride_id, local_hour
            having count(*) >= {MIN_OBS_PER_HOUR}
        ),
        ranked as (
            select *,
                   row_number() over (partition by ride_id order by avg_wait, local_hour) as best_rank,
                   row_number() over (partition by ride_id order by avg_wait desc, local_hour) as worst_rank
            from hourly
        )
        select
            q.park_name, q.ride_name, q.land_name,
            round(avg(q.wait_time), 1)  as avg_wait,
            max(q.wait_time)            as max_wait,
            count(*)                    as obs,
            any_value(b.local_hour)     as best_hour,
            round(any_value(b.avg_wait), 1) as best_hour_wait,
            any_value(w.local_hour)     as worst_hour,
            round(any_value(w.avg_wait), 1) as worst_hour_wait
        from queued q
        left join ranked b on b.ride_id = q.ride_id and b.best_rank = 1
        left join ranked w on w.ride_id = q.ride_id and w.worst_rank = 1
        group by q.park_name, q.ride_name, q.land_name
        order by avg_wait desc
    """)

    return {"meta": meta, "latest": latest, "park_now": park_now, "by_hour": by_hour,
            "by_weekday": by_weekday, "rides": rides}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()

    summary = build(args.raw)
    reports = args.out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "summary.json").write_text(json.dumps(summary, indent=1))
    template = Path(__file__).with_name("dashboard_template.html").read_text(encoding="utf-8")
    html = template.replace("__DATA__", json.dumps(summary).replace("</", "<\\/"))
    (args.out / "index.html").write_text(html, encoding="utf-8")
    m = summary["meta"]
    print(f"{m['snapshots']} snapshots over {m['days']} day(s), {m['queued_attractions']} queued attractions -> index.html")


if __name__ == "__main__":
    main()

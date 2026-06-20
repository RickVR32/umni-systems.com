#!/usr/bin/env python3
"""
export_reports.py — UMNi-HUB

Reads the `trades` table in umni_assist.db and writes reports.json,
the data file the public /reports page reads.

Run this on a schedule (cron, or a daily ARIA command) so the page
stays current. Designed to be safe to run repeatedly — it's a pure
read + overwrite, no state mutation in the DB.

Usage:
    python3 export_reports.py
    python3 export_reports.py --db /path/to/umni_assist.db --out /path/to/reports.json
"""
import sqlite3
import json
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="umni_assist.db")
    p.add_argument("--out", default="reports.json")
    return p.parse_args()


def week_bounds(dt: datetime):
    """Return (Monday, Sunday) for the week containing dt, as date strings."""
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return monday.date().isoformat(), sunday.date().isoformat()


def empty_stats():
    return {"trades": 0, "wins": 0, "losses": 0, "be": 0,
            "total_pips": 0.0, "total_net": 0.0, "win_rate": 0.0}


def fold_trade(stats: dict, net: float, pips: float):
    stats["trades"] += 1
    if net > 0.5:
        stats["wins"] += 1
    elif net < -0.5:
        stats["losses"] += 1
    else:
        stats["be"] += 1
    stats["total_pips"] += pips or 0.0
    stats["total_net"] += net or 0.0


def finalize_stats(stats: dict):
    decided = stats["wins"] + stats["losses"]
    stats["win_rate"] = round((stats["wins"] / decided) * 100, 1) if decided else 0.0
    stats["total_pips"] = round(stats["total_pips"], 1)
    stats["total_net"] = round(stats["total_net"], 2)
    return stats


def main():
    args = parse_args()
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT symbol, direction, net, pips, reason, source,
               close_time, created_at
        FROM trades
        ORDER BY close_time ASC
    """)
    rows = cur.fetchall()

    all_time = empty_stats()
    by_source_alltime = defaultdict(empty_stats)
    weekly = {}  # week_start -> {"week_start", "week_end", "overall", "by_source": {...}}
    recent = []

    for row in rows:
        net = row["net"] or 0.0
        pips = row["pips"] or 0.0
        source = row["source"] or "UNKNOWN"
        close_time_raw = row["close_time"] or row["created_at"]

        try:
            close_dt = datetime.fromisoformat(close_time_raw.replace("Z", "+00:00"))
        except Exception:
            close_dt = datetime.now(timezone.utc)

        fold_trade(all_time, net, pips)
        fold_trade(by_source_alltime[source], net, pips)

        wk_start, wk_end = week_bounds(close_dt)
        if wk_start not in weekly:
            weekly[wk_start] = {
                "week_start": wk_start,
                "week_end": wk_end,
                "overall": empty_stats(),
                "by_source": defaultdict(empty_stats),
            }
        fold_trade(weekly[wk_start]["overall"], net, pips)
        fold_trade(weekly[wk_start]["by_source"][source], net, pips)

        recent.append({
            "date": close_dt.strftime("%Y-%m-%d %H:%M"),
            "symbol": row["symbol"],
            "direction": row["direction"],
            "source": source,
            "pips": round(pips, 1),
            "net": round(net, 2),
            "reason": row["reason"] or "",
        })

    # finalize aggregates
    finalize_stats(all_time)
    for s in by_source_alltime.values():
        finalize_stats(s)

    weekly_list = []
    for wk in sorted(weekly.values(), key=lambda w: w["week_start"], reverse=True):
        finalize_stats(wk["overall"])
        wk["by_source"] = {src: finalize_stats(s) for src, s in wk["by_source"].items()}
        weekly_list.append(wk)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_time": all_time,
        "by_source_all_time": dict(by_source_alltime),
        "weekly": weekly_list,
        "recent_trades": list(reversed(recent))[:30],  # most recent first, capped
    }

    with open(args.out, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {args.out}: {all_time['trades']} total trades, "
          f"{len(weekly_list)} week(s), {len(by_source_alltime)} source(s).")


if __name__ == "__main__":
    main()

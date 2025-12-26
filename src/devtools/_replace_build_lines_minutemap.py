# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
text = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

new_fn = r"""
def build_lines_strict(jobs):
    from datetime import datetime, timezone

    def to_utc_dt(ts):
        # ts may be in seconds or milliseconds
        if ts > 10_000_000_000:  # ms heuristic
            ts = ts // 1000
        # use timezone-aware UTC (avoid deprecation)
        return datetime.fromtimestamp(int(ts), timezone.utc)

    lines = []
    matched = 0
    total_jobs = len(jobs)

    for parts in jobs:
        if len(parts) == 9:
            mint, hhmm, invest, *_ = parts
        elif len(parts) >= 10:
            mint, hhmm, mc, invest, *_ = parts
        else:
            continue

        try:
            net, pool = detect_network_and_pool(mint)
            candles = fetch_ohlcv_1m_last_48h(net, pool)
            if not candles:
                continue

            # Build a map of (HH,MM)->ts by scanning ALL candles (not just a small sample)
            minute_to_ts = {}
            for c in candles:
                try:
                    ts = c[0]
                    dt = to_utc_dt(ts)
                    key = (dt.hour, dt.minute)
                    # keep the earliest ts we see for that minute (open time)
                    if key not in minute_to_ts:
                        minute_to_ts[key] = ts
                except Exception:
                    continue

            try:
                hh, mm = [int(x) for x in hhmm.split(":")]
            except Exception:
                # if bad hh:mm, skip
                continue

            # search exact + ±1..±5 min tolerance with hour wrap
            found_ts = None
            for delta in (0,1,2,3,4,5,-1,-2,-3,-4,-5):
                hh2, mm2 = hh, mm + delta
                # normalize minutes with hour wrap
                while mm2 >= 60:
                    mm2 -= 60
                    hh2 = (hh2 + 1) % 24
                while mm2 < 0:
                    mm2 += 60
                    hh2 = (hh2 - 1) % 24
                if (hh2 % 24, mm2) in minute_to_ts:
                    found_ts = minute_to_ts[(hh2 % 24, mm2)]
                    break

            if found_ts is None:
                # richer debug: show a few minutes that exist at the target hour
                try:
                    avail = sorted({ m for (h, m) in minute_to_ts.keys() if h == hh })[:15]
                    print(f"[strict-match debug] no HH:MM for {hh:02d}:{mm:02d} UTC; available minutes at hour {hh:02d}: {avail}")
                except Exception:
                    pass
                continue

            lines.append((mint, hhmm, float(invest), "realistic", candles))
            matched += 1

        except Exception:
            continue

    return lines, matched, total_jobs
"""

# Replace the entire build_lines_strict definition (the clean one we added earlier)
pat = re.compile(r"^\s*def\s+build_lines_strict\s*\([^)]*\)\s*:[\s\S]*?(?=^\s*def\s+|\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:|\Z)", re.MULTILINE)
if pat.search(text):
    text = pat.sub(new_fn + "\n", text, count=1)
    print("Replaced build_lines_strict() with minute-map matcher.")
else:
    print("Could not locate build_lines_strict(); no change made.")

io.open(P, "w", encoding="utf-8", newline="\n").write(text)
print("Saved ai_strategy_finder.py (UTF-8, LF).")

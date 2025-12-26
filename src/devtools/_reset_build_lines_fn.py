# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
src = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

NEW_FN = r"""
def build_lines_strict(jobs):
    from datetime import datetime, timezone
    import os as _os

    def extract_ts(c):
        try:
            if isinstance(c, dict):
                for k in ("ts","timestamp","time","t","open_time","openTime"):
                    if k in c:
                        v = int(c[k])
                        return v//1000 if v > 10_000_000_000 else v
            if isinstance(c, (list, tuple)) and c:
                for idx in range(min(4, len(c))):
                    v = c[idx]
                    if isinstance(v, (int, float)):
                        iv = int(v)
                        if iv > 10_000_000_000:
                            return iv//1000
                        if 1_000_000_000 <= iv <= 20_000_000_000:
                            return iv
        except Exception:
            pass
        return None

    def to_utc_dt(ts):
        return datetime.fromtimestamp(int(ts), timezone.utc)

    def minute_map(candles):
        m = {}
        for c in candles:
            ts = extract_ts(c)
            if ts is None:
                continue
            dt = to_utc_dt(ts)
            key = (dt.hour, dt.minute)
            if key not in m:  # keep first seen (open) for that minute
                m[key] = ts
        return m

    lines = []
    matched = 0
    total_jobs = len(jobs)

    strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"
    input_tz = _os.environ.get("TB_INPUT_TZ", "UTC").upper()

    for parts in jobs:
        if len(parts) == 9:
            mint, hhmm, invest, *_ = parts
        elif len(parts) >= 10:
            mint, hhmm, mc, invest, *_ = parts
        else:
            continue

        try:
            net, pool = detect_network_and_pool(mint)
            # you already swapped this to 7d in your file; keep it here too:
            candles = fetch_ohlcv_1m_last_7d(net, pool)
            if not candles:
                continue

            mm_map = minute_map(candles)

            try:
                hh, mmn = [int(x) for x in hhmm.split(":")]
            except Exception:
                continue

            # configure input timezone → UTC hour
            hh_input_utc = (hh - 5) % 24 if input_tz == "KHI" else hh

            # try_match uses TB_STRICT_EXACT internally (0 => ±5, 1 => exact only)
            found = try_match(mm_map, hh_input_utc, mmn)

            # nearest-hour fallback only when NOT strict
            if (not strict) and (found is None):
                hours_present = sorted({h for (h, _m) in mm_map.keys()})
                if hours_present:
                    def hour_dist(a,b):
                        d = abs(a-b) % 24
                        return min(d, 24-d)
                    best_hour = min(hours_present, key=lambda H: hour_dist(H, hh_input_utc))
                    # try same minute at nearest hour (±5)
                    found = try_match(mm_map, best_hour, mmn)
                    if found is None:
                        mins_at_hour = sorted({m for (H, m) in mm_map.keys() if H == best_hour})
                        if mins_at_hour:
                            fallback_min = mins_at_hour[0]
                            found = mm_map.get((best_hour, fallback_min))
                            print(f"[strict-match fallback] using {best_hour:02d}:{fallback_min:02d} UTC (nearest hour to {hh_input_utc:02d}:{mmn:02d})")

            if found is None:
                continue

            dt_found = datetime.fromtimestamp(int(found), timezone.utc)
            hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"
            lines.append((mint, hhmm_use, float(invest), "realistic", candles))
            matched += 1

        except Exception:
            continue

    return lines, matched, total_jobs
"""

# Replace entire build_lines_strict definition with NEW_FN
pat = re.compile(r"^\s*def\s+build_lines_strict\s*\([^)]*\)\s*:[\s\S]*?(?=^\s*def\s+|\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:|\Z)", re.MULTILINE)
if pat.search(src):
    src = pat.sub(NEW_FN + "\n", src, count=1)
    print("Replaced build_lines_strict() with a clean, consistent version.")
else:
    # Insert above main guard if not found
    m = re.search(r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*$", src, re.MULTILINE)
    if m:
        src = src[:m.start()] + NEW_FN + "\n" + src[m.start():]
        print("Inserted build_lines_strict() above __main__ guard.")
    else:
        src = src.rstrip() + "\n\n" + NEW_FN + "\n"
        print("Appended build_lines_strict() at EOF.")

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("Saved ai_strategy_finder.py (UTF-8, LF).")

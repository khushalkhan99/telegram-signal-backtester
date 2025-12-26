# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
text = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

new_fn = r"""
def build_lines_strict(jobs):
    from datetime import datetime, timezone

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
            if key not in m:
                m[key] = ts
        return m

    def try_match(mm, hh, mmn):
        for delta in (0,1,2,3,4,5,-1,-2,-3,-4,-5):
            h2, m2 = hh, mmn + delta
            while m2 >= 60:
                m2 -= 60
                h2 = (h2 + 1) % 24
            while m2 < 0:
                m2 += 60
                h2 = (h2 - 1) % 24
            ts = mm.get((h2 % 24, m2))
            if ts is not None:
                return ts
        return None

    def hour_dist(a,b):
        d = abs(a-b) % 24
        return min(d, 24-d)

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

            mm_map = minute_map(candles)

            # one-time debug
            try:
                if '___mm_debug_printed' not in globals():
                    globals()['___mm_debug_printed'] = True
                    uniq_hours = sorted({h for (h, m) in mm_map.keys()})
                    sample_minutes = {h: sorted({m for (hh, m) in mm_map.keys() if hh == h})[:10] for h in uniq_hours[:5]}
                    print(f"[candles debug] candles_len={len(candles)} minute_map_size={len(mm_map)} hours_present={uniq_hours[:24]}")
                    print(f"[candles debug] sample minutes per first hours: {sample_minutes}")
                    raw_ts = []
                    for c in candles[:3]:
                        v = None
                        if isinstance(c, dict):
                            for k in ('ts','timestamp','time','t','open_time','openTime'):
                                if k in c:
                                    v = c[k]; break
                        elif isinstance(c, (list, tuple)) and len(c) > 0:
                            v = c[0]
                        raw_ts.append(v)
                    print(f"[candles debug] first3_raw_ts_fields={raw_ts}")
            except Exception:
                pass

            try:
                hh, mmn = [int(x) for x in hhmm.split(":")]
            except Exception:
                continue

            # 1) UTC direct
            found = try_match(mm_map, hh, mmn)
            # 2) KHI->UTC
            if found is None:
                found = try_match(mm_map, (hh - 5) % 24, mmn)
            # 3) Nearest-hour fallback
            if found is None:
                hours_present = sorted({h for (h, _m) in mm_map.keys()})
                if hours_present:
                    candidates = [hh, (hh - 5) % 24]
                    best_hour = min(
                        hours_present,
                        key=lambda H: min(hour_dist(H, candidates[0]), hour_dist(H, candidates[1]))
                    )
                    found = try_match(mm_map, best_hour, mmn)
                    if found is None:
                        mins_at_hour = sorted({m for (H, m) in mm_map.keys() if H == best_hour})
                        if mins_at_hour:
                            fallback_min = mins_at_hour[0]
                            found = mm_map.get((best_hour, fallback_min))
                            print(f"[strict-match fallback] using {best_hour:02d}:{fallback_min:02d} UTC (nearest hour to {hh:02d}:{mmn:02d})")

            if found is None:
                continue

            lines.append((mint, hhmm, float(invest), "realistic", candles))
            matched += 1

        except Exception:
            continue

    return lines, matched, total_jobs
"""

pat = re.compile(r"^\s*def\s+build_lines_strict\s*\([^)]*\)\s*:[\s\S]*?(?=^\s*def\s+|\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:|\Z)", re.MULTILINE)
if pat.search(text):
    text = pat.sub(new_fn + "\n", text, count=1)
    print("Replaced build_lines_strict() with nearest-hour fallback version.")
else:
    print("Could not locate build_lines_strict(); no change made.")

io.open(P, "w", encoding="utf-8", newline="\n").write(text)
print("Saved ai_strategy_finder.py (UTF-8, LF).")

# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
text = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

new_fn = r"""
def build_lines_strict(jobs):
    from datetime import datetime, timezone

    def extract_ts(c):
        # Return epoch seconds (int) or None
        try:
            # dict-like
            if isinstance(c, dict):
                for k in ("ts","timestamp","time","t","open_time","openTime"):
                    if k in c:
                        v = int(c[k])
                        if v > 10_000_000_000:  # ms
                            return v // 1000
                        return v
            # list/tuple-like
            if isinstance(c, (list, tuple)):
                # try first few fields to find a plausible epoch
                for idx in range(min(4, len(c))):
                    v = c[idx]
                    if isinstance(v, (int, float)):
                        iv = int(v)
                        # seconds ~ 1.6e9, ms ~ 1.6e12 (2025)
                        if iv > 10_000_000_000:       # looks like ms
                            return iv // 1000
                        if 1_000_000_000 <= iv <= 20_000_000_000:  # looks like seconds
                            return iv
        except Exception:
            pass
        return None

    def to_utc_dt(ts):
        # ts is epoch seconds
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

    def try_match(minute_to_ts, hh, mm):
        # exact + ±1..±5 with wrap
        for delta in (0,1,2,3,4,5,-1,-2,-3,-4,-5):
            hh2, mm2 = hh, mm + delta
            while mm2 >= 60:
                mm2 -= 60
                hh2 = (hh2 + 1) % 24
            while mm2 < 0:
                mm2 += 60
                hh2 = (hh2 - 1) % 24
            ts = minute_to_ts.get((hh2 % 24, mm2))
            if ts is not None:
                return ts
        return None

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

            # parse HH:MM from job
            try:
                hh, mm = [int(x) for x in hhmm.split(":")]
            except Exception:
                continue

            # 1) Treat HH:MM as UTC
            found = try_match(mm_map, hh, mm)

            # 2) If not found, also try assuming HH:MM is Asia/Karachi (UTC+5) → convert to UTC
            if found is None:
                hh_khi_to_utc = (hh - 5) % 24
                found = try_match(mm_map, hh_khi_to_utc, mm)

            if found is None:
                # Richer debug: show a few minutes that exist at both candidate hours
                try:
                    avail_utc = sorted({m for (h, m) in mm_map.keys() if h == hh})[:15]
                    avail_khi = sorted({m for (h, m) in mm_map.keys() if h == ((hh - 5) % 24)})[:15]
                    print(f"[strict-match debug] no match for {hh:02d}:{mm:02d} as UTC or KHI→UTC; "
                          f"UTC hour {hh:02d} minutes: {avail_utc}; "
                          f"KHI→UTC hour {(hh-5)%24:02d} minutes: {avail_khi}")
                except Exception:
                    pass
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
    print("Replaced build_lines_strict() with robust timestamp + timezone matcher.")
else:
    print("Could not locate build_lines_strict(); no change made.")

io.open(P, "w", encoding="utf-8", newline="\n").write(text)
print("Saved ai_strategy_finder.py (UTF-8, LF).")

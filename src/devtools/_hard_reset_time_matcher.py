# -*- coding: utf-8 -*-
import io, os, re

P = os.path.join("src","ai_strategy_finder.py")
src = io.open(P, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

# Remove any existing try_match/build_lines_strict definitions.
def drop_def(text, name):
    pat = re.compile(
        rf"^\s*def\s+{name}\s*\([^)]*\)\s*:[\s\S]*?(?=^\s*def\s+|\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:|\Z)",
        re.MULTILINE
    )
    return pat.sub("", text)

src = drop_def(src, "try_match")
src = drop_def(src, "build_lines_strict")

# Insert fresh, strict versions right above __main__ guard (or append).
new_block = r"""
def try_match(mm, hh, mmn):
    \"\"\"Strict exact-minute only: returns ts if (hh,mm) exists, else None.\"\"\"
    return mm.get(((hh % 24), mmn), None)

def build_lines_strict(jobs):
    \"\"\"Build lines with strict exact HH:MM matching.
    - Input HH:MM interpreted via TB_INPUT_TZ (UTC|KHI). Default UTC.
    - Lookback default: last 48h (fetch_ohlcv_1m_last_48h).
      If TB_LOOKBACK='7d', uses fetch_ohlcv_1m_last_7d instead.
    Returns (lines, matched, total_jobs).
    \"\"\"
    from datetime import datetime, timezone
    import os as _os

    def _extract_ts(c):
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

    def _minute_map(candles):
        m = {}
        for c in candles:
            ts = _extract_ts(c)
            if ts is None:
                continue
            # store earliest ts for that minute (open)
            dt = datetime.fromtimestamp(int(ts), timezone.utc)
            key = (dt.hour, dt.minute)
            if key not in m:
                m[key] = ts
        return m

    lines = []
    matched = 0
    total_jobs = len(jobs)

    input_tz = (_os.environ.get("TB_INPUT_TZ", "UTC") or "UTC").upper()
    lookback = (_os.environ.get("TB_LOOKBACK", "48h") or "48h").lower()
    use_7d = (lookback == "7d")

    for parts in jobs:
        if len(parts) == 9:
            mint, hhmm, invest, *_ = parts
        elif len(parts) >= 10:
            mint, hhmm, mc, invest, *_ = parts
        else:
            continue

        try:
            net, pool = detect_network_and_pool(mint)
            candles = fetch_ohlcv_1m_last_7d(net, pool) if use_7d else fetch_ohlcv_1m_last_48h(net, pool)
            if not candles:
                continue

            mm_map = _minute_map(candles)

            # parse HH:MM
            try:
                hh, mm = [int(x) for x in hhmm.split(":")]
            except Exception:
                continue

            # convert to UTC hour if input is Karachi
            hh_utc = (hh - 5) % 24 if input_tz == "KHI" else hh

            found = try_match(mm_map, hh_utc, mm)
            if found is None:
                # strict mode: if exact minute not present, skip
                # (we do NOT do any ±tolerance or nearest-hour fallback)
                # Optional: print a once-per-run hint for visibility
                if "_STRICT_MISS_SHOWN" not in globals():
                    globals()["_STRICT_MISS_SHOWN"] = True
                    avail_hours = sorted({h for (h, _m) in mm_map.keys()})
                    print(f"[strict] exact minute not found; available UTC hours in lookback: {avail_hours}")
                continue

            # pass the exact matched minute downstream (UTC hh:mm)
            from datetime import timezone
            dt_found = datetime.fromtimestamp(int(found), timezone.utc)
            hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"
            lines.append((mint, hhmm_use, float(invest), "realistic", candles))
            matched += 1

        except Exception:
            continue

    return lines, matched, total_jobs
"""

m = re.search(r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*$", src, re.MULTILINE)
if m:
    src = src[:m.start()] + new_block + "\n" + src[m.start():]
else:
    src = src.rstrip() + "\n\n" + new_block + "\n"

io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("Hard-reset strict time matcher (exact only, 48h default, optional 7d via TB_LOOKBACK).")

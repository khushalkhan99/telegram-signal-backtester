# -*- coding: utf-8 -*-
import io, os, re, textwrap

ROOT = os.path.join("src")
MAIN = os.path.join(ROOT, "ai_strategy_finder.py")
HELP = os.path.join(ROOT, "_lines_builder.py")

# 1) Write clean helper module with robust logic.
helper_code = r"""
# -*- coding: utf-8 -*-
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

def _to_utc_dt(ts: int):
    return datetime.fromtimestamp(int(ts), timezone.utc)

def _minute_map(candles):
    m = {}
    for c in candles:
        ts = _extract_ts(c)
        if ts is None:
            continue
        dt = _to_utc_dt(ts)
        key = (dt.hour, dt.minute)
        if key not in m:  # keep first (open) per minute
            m[key] = ts
    return m

def try_match(mm, hh, mmn):
    strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"
    deltas = (0,) if strict else (0,1,2,3,4,5,-1,-2,-3,-4,-5)
    for delta in deltas:
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

def build_lines_strict(jobs, detect_network_and_pool, fetch_ohlcv_1m_last_7d):
    """
    Returns: (lines, matched, total_jobs)
    lines item shape matches the original: (mint, hhmm, invest_float, "realistic", candles)
    """
    input_tz = _os.environ.get("TB_INPUT_TZ", "UTC").upper()
    strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"

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
            candles = fetch_ohlcv_1m_last_7d(net, pool)
            if not candles:
                continue

            mm_map = _minute_map(candles)

            try:
                hh, mmn = [int(x) for x in hhmm.split(":")]
            except Exception:
                continue

            hh_input_utc = (hh - 5) % 24 if input_tz == "KHI" else hh

            found = try_match(mm_map, hh_input_utc, mmn)

            # nearest-hour fallback only when not strict
            if (not strict) and (found is None):
                hours_present = sorted({h for (h, _m) in mm_map.keys()})
                if hours_present:
                    def _hour_dist(a,b):
                        d = abs(a-b) % 24
                        return min(d, 24-d)
                    best_hour = min(hours_present, key=lambda H: _hour_dist(H, hh_input_utc))
                    found = try_match(mm_map, best_hour, mmn)
                    if found is None:
                        mins_at_hour = sorted({m for (H, m) in mm_map.keys() if H == best_hour})
                        if mins_at_hour:
                            fallback_min = mins_at_hour[0]
                            found = mm_map.get((best_hour, fallback_min))

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

os.makedirs(ROOT, exist_ok=True)
io.open(HELP, "w", encoding="utf-8", newline="\n").write(helper_code)
print("Wrote src/_lines_builder.py")

# 2) Replace in-file try_match/build_lines_strict with tiny stubs that delegate to helper.
text = io.open(MAIN, "r", encoding="utf-8", errors="replace").read().replace("\t","    ")

def replace_def(name, params, body):
    pat = re.compile(rf"^\s*def\s+{name}\s*\([^\)]*\)\s*:[\s\S]*?(?=^\s*def\s+|\nif\s+__name__\s*==\s*['\"]__main__['\"]\s*:|\Z)", re.MULTILINE)
    stub = f\"\"\"\n\ndef {name}{params}:\n{body}\n\"\"\"\n
    if pat.search(text):
        return pat.sub(stub, text, count=1), True
    else:
        # If not found, just append the stub
        return text.rstrip() + stub, False

# try_match stub
stub_body_try = textwrap.indent(
    "from _lines_builder import try_match as _t\n"
    "return _t(mm, hh, mmn)\n",
    "    "
)
text, _ = replace_def("try_match", "(mm, hh, mmn)", stub_body_try)

# build_lines_strict stub
stub_body_build = textwrap.indent(
    "from _lines_builder import build_lines_strict as _b\n"
    "return _b(jobs, detect_network_and_pool, fetch_ohlcv_1m_last_7d)\n",
    "    "
)
text, _ = replace_def("build_lines_strict", "(jobs)", stub_body_build)

io.open(MAIN, "w", encoding="utf-8", newline="\n").write(text)
print("Replaced in-file try_match/build_lines_strict with clean stubs -> helper module.")

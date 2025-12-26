# -*- coding: utf-8 -*-
import os, sys, time, json, math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timezone
import httpx

# -------- Config (reads TB_* envs) --------
SLIP = float(os.getenv("TB_SLIP", "0.0"))
SLIP_MODE = os.getenv("TB_SLIP_MODE", "amount")      # "price" | "amount"
SLIP_SIDE = os.getenv("TB_SLIP_SIDE", "sell")        # "both" | "buy" | "sell"
BUY_FEE = float(os.getenv("TB_BUY_FEE", "0.005"))    # fraction
SELL_FEE = float(os.getenv("TB_SELL_FEE", "0.005"))  # fraction

API_ROOT = "https://api.geckoterminal.com/api/v2"
NETWORKS = ["solana","bsc","eth","base"]
CACHE_DIR = os.path.join("cache","ohlcv_1m_48h")
os.makedirs(CACHE_DIR, exist_ok=True)

# -------- HTTP / data fetch --------
def http_get(url, params=None):
    r = httpx.get(url, params=params or {}, headers={"accept":"application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

def detect_network_and_pool(mint: str) -> Tuple[str,str]:
    for net in NETWORKS:
        try:
            js = http_get(f"{API_ROOT}/networks/{net}/tokens/{mint}/pools", {"page": 1})
        except Exception:
            continue
        data = js.get("data") or []
        if data:
            addr = data[0].get("attributes", {}).get("address")
            if addr:
                return net, addr
    raise RuntimeError(f"No pools found for {mint} across {NETWORKS}")

def fetch_ohlcv_1m_last_7d(network: str, pool: str):
    cache_path = os.path.join(CACHE_DIR, f"{network}_{pool}.json")
    now = int(time.time())
    if os.path.isfile(cache_path):
        try:
            js = json.load(open(cache_path, "r", encoding="utf-8"))
            if js and isinstance(js, list):
                if js and (now - int(js[-1][0])) < 600:
                    return js
        except Exception:
            pass

    url = f"{API_ROOT}/networks/{network}/pools/{pool}/ohlcv/minute"
    out = []
    cutoff = now - 48*60*60
    before = now + 60
    for _ in range(6):
        resp = http_get(url, {"aggregate":1, "limit":500, "before_timestamp": before})
        attrs = (resp.get("data") or {}).get("attributes", {})
        lst = attrs.get("ohlcv_list") or []
        if not lst: break
        out.extend(lst)
        oldest = int(lst[0][0])
        before = oldest
        if oldest <= cutoff: break
        time.sleep(0.15)
    out.sort(key=lambda r: int(r[0]))
    out = [r for r in out if int(r[0]) >= cutoff]

    try:
        json.dump(out, open(cache_path, "w", encoding="utf-8"))
    except Exception:
        pass
    return out

# -------- Helpers --------
def find_entry_minute(candles, hh: int, mm: int):
    """
    Strict: require an exact HH:MM (UTC) candle within last 48h.
    Return latest matching ts, or None if not present.
    """
    now = int(time.time()); cutoff = now - 48*60*60
    exact = []
    for ts, *_ in candles:
        ts = int(ts)
        if not (cutoff <= ts <= now):
            continue
        t = datetime.fromtimestamp(ts, tz=timezone.utc)
        if t.hour == hh and t.minute == mm:
            exact.append(ts)
    return max(exact) if exact else None

def entry_fill(o,h,l,c, mode: str):
    lo, hi = float(l), float(h)
    op, cl = float(o), float(c)
    rng_up = max(0.0, hi - op)
    rng_dn = max(0.0, op - lo)
    is_green = cl >= op
    if mode == "optimistic":
        raw = op
    elif mode == "realistic":
        raw = op + (0.30*rng_up if is_green else -0.30*rng_dn)
    elif mode == "pessimistic":
        raw = hi
    else:
        raise RuntimeError("mode must be optimistic|realistic|pessimistic")
    return max(lo, min(hi, raw))

def execute_buy(raw_price, invest_usd):
    buy_fee_usd = invest_usd * BUY_FEE
    cash_after_fee = invest_usd - buy_fee_usd
    if SLIP_SIDE in ("both","buy"):
        if SLIP_MODE == "price":
            paid_entry_px = raw_price * (1.0 + SLIP)
            qty = cash_after_fee / paid_entry_px
            return qty, paid_entry_px, buy_fee_usd
        else:
            eff_cash = cash_after_fee * (1.0 - SLIP)
            qty = eff_cash / raw_price
            return qty, raw_price, buy_fee_usd
    qty = cash_after_fee / raw_price
    return qty, raw_price, buy_fee_usd

def sell_proceeds_amount_mode(raw_price, qty):
    gross = qty * raw_price
    sell_fee_usd = gross * SELL_FEE
    after_fee = gross - sell_fee_usd
    if SLIP_SIDE in ("both","sell"):
        if SLIP_MODE == "price":
            recv_px = raw_price * (1.0 - SLIP)
            proceeds = qty * recv_px * (1.0 - SELL_FEE)
            sell_fee_usd = qty * recv_px * SELL_FEE
            return proceeds, sell_fee_usd
        else:
            proceeds = after_fee * (1.0 - SLIP)
            return proceeds, sell_fee_usd
    return after_fee, sell_fee_usd

from dataclasses import dataclass

@dataclass(frozen=True)
class Strategy:
    use_tsl: bool              # False=SL, True=TSL
    tps: Tuple[float,...]      # thresholds over paid entry (e.g. (0.05, 0.15))
    sizes: Tuple[float,...]    # position fractions for each TP (sum <= 1.0)
    stop: float                # if SL: stop-down; if TSL: trailing percent
    mode: str = "realistic"

def simulate_line(candles, hhmm: str, invest: float, mode: str, strat: Strategy):
    hh, mm = [int(x) for x in hhmm.split(":")]
    entry_ts = find_entry_minute(candles, hh, mm)
    if not entry_ts:
        return None
    idx = next(i for i, r in enumerate(candles) if int(r[0]) == entry_ts)
    ts, o,h,l,c = int(candles[idx][0]), float(candles[idx][1]), float(candles[idx][2]), float(candles[idx][3]), float(candles[idx][4])

    raw_entry = entry_fill(o,h,l,c, mode)
    qty, paid_entry, buy_fee_usd = execute_buy(raw_entry, invest)

    tp_levels = [paid_entry * (1.0 + x) for x in strat.tps]
    sl_level = paid_entry * (1.0 - strat.stop) if not strat.use_tsl else None
    trail_peak = paid_entry
    tsl_stop = paid_entry * (1.0 - strat.stop) if strat.use_tsl else None

    remaining = qty
    proceeds = 0.0
    sell_fee_total = 0.0
    max_high = float(h)
    last_ts = ts

    for j in range(idx, min(idx + 2000, len(candles))):
        ts2, o2,h2,l2,c2 = int(candles[j][0]), float(candles[j][1]), float(candles[j][2]), float(candles[j][3]), float(candles[j][4])
        last_ts = ts2
        max_high = max(max_high, h2)

        if strat.use_tsl:
            trail_peak = max(trail_peak, h2)
            tsl_stop = trail_peak * (1.0 - strat.stop)

        # try TP fills in order
        for k in range(len(tp_levels)):
            if remaining <= 0: break
            if strat.sizes[k] <= 0: continue
            if h2 >= tp_levels[k]:
                sub_qty = qty * strat.sizes[k]
                sub_qty = min(sub_qty, remaining)
                sub_proceeds, sub_fee = sell_proceeds_amount_mode(o2, sub_qty)
                proceeds += sub_proceeds
                sell_fee_total += sub_fee
                remaining -= sub_qty
                tp_levels[k] = float("inf")

        if remaining <= 0:
            break

        # stop decisions
        if strat.use_tsl:
            if l2 <= tsl_stop:
                sub_qty = remaining
                sub_proceeds, sub_fee = sell_proceeds_amount_mode(o2, sub_qty)
                proceeds += sub_proceeds
                sell_fee_total += sub_fee
                remaining = 0
                break
        else:
            if l2 <= sl_level:
                sub_qty = remaining
                sub_proceeds, sub_fee = sell_proceeds_amount_mode(o2, sub_qty)
                proceeds += sub_proceeds
                sell_fee_total += sub_fee
                remaining = 0
                break

    if remaining > 0:
        ts2, o2,h2,l2,c2 = int(candles[-1][0]), float(candles[-1][1]), float(candles[-1][2]), float(candles[-1][3]), float(candles[-1][4])
        sub_qty = remaining
        sub_proceeds, sub_fee = sell_proceeds_amount_mode(c2, sub_qty)
        proceeds += sub_proceeds
        sell_fee_total += sub_fee
        remaining = 0
        last_ts = ts2
        max_high = max(max_high, h2)

    pnl_usd = proceeds - invest - buy_fee_usd
    hold_min = max(0, int((last_ts - ts)/60))
    ath_mult = (max_high / raw_entry) if raw_entry > 0 else 0.0
    return pnl_usd, hold_min, ath_mult

# -------- Runner --------
def clean_parts(line: str):
    line = line.strip()
    if not line or line.lstrip().startswith("#"):
        return None
    parts = [p.strip() for p in (line.split("|") if "|" in line else line.split(","))]
    parts = [p for p in parts if p]
    return parts

def run():
    batch_file = os.path.join("src","batch_lines.txt")
    try:
        raw = open(batch_file, "r", encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        print("missing src/batch_lines.txt"); sys.exit(2)
    jobs = [clean_parts(ln) for ln in raw]
    jobs = [p for p in jobs if p]
    if not jobs:
        print("no jobs in batch_lines.txt"); sys.exit(3)
    lines, matched, total_jobs = build_lines_strict(jobs)
    print(f"Matched {matched} of {total_jobs} lines (±1 min tolerance). Skipped {total_jobs - matched}.")
    if not lines:
        print("no valid lines to simulate"); sys.exit(3)

    # summary of matches
    print(f"Matched {len(lines)} of {len(jobs)} lines (exact HH:MM). Skipped {len(jobs)-len(lines)} with no exact candle.")

    # Strategy space: 1 TP, 2 TP, 3 TP; SL and TSL; a few stops
    tp_grids = [
        ((0.05,),        ((1.0,), (0.7,), (0.5,))),
        ((0.05, 0.15),   ((0.5,0.5), (0.7,0.3))),
        ((0.05, 0.15, 0.30), ((0.4,0.3,0.3), (0.5,0.3,0.2))),
    ]
    stops = [0.05, 0.08, 0.10]
    use_tsl_opts = [False, True]

    strategies: List[Strategy] = []
    for tps, size_sets in tp_grids:
        for sizes in size_sets:
            if sum(sizes) > 1.0 + 1e-9:
                continue
            for st in stops:
                for use_tsl in use_tsl_opts:
                    strategies.append(Strategy(use_tsl=use_tsl, tps=tps, sizes=sizes, stop=st))

    print(f"Testing {len(strategies)} strategies across {len(lines)} lines...")

    totals: Dict[Strategy, float] = {s:0.0 for s in strategies}
    holds: Dict[Strategy, List[int]] = {s:[] for s in strategies}

    for (mint, hhmm, invest, mode, candles) in lines:
        for s in strategies:
            res = simulate_line(candles, hhmm, invest, mode, s)
            if res is None:
                continue
            pnl_usd, hold_min, _ath = res
            totals[s] += pnl_usd
            holds[s].append(hold_min)

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:3]

    print("\n=== TOP 3 STRATEGIES (by total PnL) ===")
    for i, (s, total) in enumerate(ranked, 1):
        tp_str = " / ".join(f"{int(x*100)}%" for x in s.tps)
        sz_str = " / ".join(f"{int(x*100)}%" for x in s.sizes)
        kind = "TSL" if s.use_tsl else "SL"
        avg_hold = (sum(holds[s])/len(holds[s])) if holds[s] else 0
        print(f"{i}. {kind}  TP[{tp_str}] sz[{sz_str}] stop={int(s.stop*100)}%  --> total ${total:,.2f} | avg_hold {avg_hold:.0f}m")

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
            candles = fetch_ohlcv_1m_last_7d(net, pool)
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

            # 1) Determine input timezone
            import os as _os
            _tz = _os.environ.get("TB_INPUT_TZ", "UTC").upper()
            if _tz == "KHI":
                # Karachi HH:MM -> convert to UTC
                hh_input_utc = (hh - 5) % 24
            else:
                hh_input_utc = hh

            # 2) Try to match using configured input timezone
            found = try_match(mm_map, hh_input_utc, mmn)

            # 3) Nearest-hour fallback (only if NOT strict)
            _strict = _os.environ.get("TB_STRICT_EXACT", "0") == "1"
            if (not _strict) and (found is None):
                hours_present = sorted({h for (h, _m) in mm_map.keys()})
                if hours_present:
                    candidates = [hh_input_utc]
                    def hour_dist(a,b):
                        d = abs(a-b) % 24
                        return min(d, 24-d)
                    best_hour = min(hours_present, key=lambda H: min(hour_dist(H, c) for c in candidates))
                    found = try_match(mm_map, best_hour, mmn)
                    if found is None:
                        mins_at_hour = sorted({m for (H, m) in mm_map.keys() if H == best_hour})
                        if mins_at_hour:
                            fallback_min = mins_at_hour[0]
                            found = mm_map.get((best_hour, fallback_min))
                            print(f"[strict-match fallback] using {best_hour:02d}:{fallback_min:02d} UTC (nearest hour to {hh_input_utc:02d}:{mmn:02d})")

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

            dt_found = datetime.fromtimestamp(int(found), timezone.utc)
            hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"
            lines.append((mint, hhmm_use, float(invest), "realistic", candles))
            matched += 1

        except Exception:
            continue

    return lines, matched, total_jobs


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
            candles = fetch_ohlcv_1m_last_7d(net, pool)
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

def try_match(mm, hh, mmn):
    \"\"\"Strict exact-minute only: returns ts if (hh,mm) exists, else None.\"\"\"
    return mm.get(((hh % 24), mmn), None)

def build_lines_strict(jobs):
    \"\"\"Build lines with strict exact HH:MM matching.
    - Input HH:MM interpreted via TB_INPUT_TZ (UTC|KHI). Default UTC.
    - Lookback default: last 48h (fetch_ohlcv_1m_last_48h).
      If TB_LOOKBACK='7d', uses fetch_ohlcv_1m_last_7d instead.
    Returns (lines, matched, total_jobs).\"\"\"
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

            try:
                hh, mm = [int(x) for x in hhmm.split(":")]
            except Exception:
                continue

            hh_utc = (hh - 5) % 24 if input_tz == "KHI" else hh

            found = try_match(mm_map, hh_utc, mm)
            if found is None:
                # strict exact: skip silently (no tolerance/fallback)
                continue

            dt_found = datetime.fromtimestamp(int(found), timezone.utc)
            hhmm_use = f"{dt_found.hour:02d}:{dt_found.minute:02d}"
            lines.append((mint, hhmm_use, float(invest), "realistic", candles))
            matched += 1

        except Exception:
            continue

    return lines, matched, total_jobs




if __name__ == "__main__":
    run()



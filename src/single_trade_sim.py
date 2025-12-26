# src/single_trade_sim.py  (verbose)
import sys, time
from datetime import datetime, timezone, timedelta
import httpx

API_ROOT = "https://api.geckoterminal.com/api/v2"
NETWORKS = ["solana","bsc","eth","base"]  # use "eth" for Ethereum on GT

def http_get(url, params=None):
    print(f"[HTTP] GET {url} params={params}", flush=True)
    r = httpx.get(url, params=params or {}, headers={"accept":"application/json"}, timeout=30)
    print(f"[HTTP] status={r.status_code}", flush=True)
    r.raise_for_status()
    js = r.json()
    print(f"[HTTP] ok; keys={list(js.keys())}", flush=True)
    return js

def detect_network_and_pool(mint: str):
    print(f"[detect] mint={mint}", flush=True)
    for net in NETWORKS:
        url = f"{API_ROOT}/networks/{net}/tokens/{mint}/pools"
        try:
            js = http_get(url, {"page": 1})
        except Exception as e:
            print(f"[detect] {net} error: {e}", flush=True)
            continue
        data = js.get("data") or []
        print(f"[detect] {net} pools={len(data)}", flush=True)
        if data:
            addr = data[0].get("attributes", {}).get("address")
            if addr:
                print(f"[detect] -> use {net}/{addr}", flush=True)
                return net, addr
    raise RuntimeError("No pools found across solana/bsc/eth/base")

def fetch_ohlcv_1m_last_48h(network: str, pool: str):
    print(f"[ohlcv] fetch last 48h 1m for {network}/{pool}", flush=True)
    url = f"{API_ROOT}/networks/{network}/pools/{pool}/ohlcv/minute"
    out = []
    now = int(time.time())
    cutoff = now - 48*60*60
    before = now + 60
    for i in range(6):  # up to ~3000 minutes
        js = http_get(url, {"aggregate":1, "limit":500, "before_timestamp": before})
        attrs = (js.get("data") or {}).get("attributes", {}) 
        lst = attrs.get("ohlcv_list") or []
        print(f"[ohlcv] batch {i+1}: rows={len(lst)}", flush=True)
        if not lst:
            break
        out.extend(lst)
        oldest = int(lst[0][0])  # ascending
        before = oldest
        if oldest <= cutoff:
            break
        time.sleep(0.25)
    out.sort(key=lambda r: int(r[0]))
    out = [r for r in out if int(r[0]) >= cutoff]
    print(f"[ohlcv] total kept rows (48h): {len(out)}", flush=True)
    return out

def find_entry_minute(candles, hh: int, mm: int):
    print(f"[entry] find HH:MM={hh:02d}:{mm:02d} UTC", flush=True)
    target_ts = None
    now = int(time.time()); cutoff = now - 48*60*60
    for ts, *_ in candles:
        t = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        if t.hour == hh and t.minute == mm and cutoff <= int(ts) <= now:
            target_ts = int(ts)  # keep latest as we go
    print(f"[entry] target_ts={target_ts}", flush=True)
    return target_ts

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
    raw = max(lo, min(hi, raw))
    print(f"[fill] {mode} -> raw_entry={raw}", flush=True)
    return raw

def apply_buy_costs(px, slippage=0.03, fee_usd=1.0):
    paid = px*(1+slippage)
    print(f"[cost] buy: raw={px} -> paid={paid} (+{slippage*100:.1f}% slip) fee=${fee_usd}", flush=True)
    return paid, fee_usd

def apply_sell_costs(px, slippage=0.03, fee_usd=1.0):
    recv = px*(1-slippage)
    print(f"[cost] sell: raw={px} -> recv={recv} (-{slippage*100:.1f}% slip) fee=${fee_usd}", flush=True)
    return recv, fee_usd

def decide_exit_in_bar(bar_open, bar_high, bar_low, tp_px, sl_px, mode, ref_for_distance):
    hit_tp = bar_high >= tp_px
    hit_sl = bar_low  <= sl_px
    if hit_tp and hit_sl:
        if mode == "optimistic":
            return "TP"
        if mode == "pessimistic":
            return "SL"
        # realistic: whichever is closer to entry price
        d_tp = abs(tp_px - ref_for_distance)
        d_sl = abs(ref_for_distance - sl_px)
        return "TP" if d_tp <= d_sl else "SL"
    if hit_tp: return "TP"
    if hit_sl: return "SL"
    return None

def fmt_usd(x): return f"${x:,.2f}"

def main():
    if len(sys.argv) < 6:
        print("Usage: python src/single_trade_sim.py <mint> <HH:MM_UTC> <invest_usd> <tp_pct_up> <sl_pct_down> [mode]")
        sys.exit(1)

    mint = sys.argv[1].strip()
    hhmm = sys.argv[2].strip()
    invest = float(sys.argv[3])
    tp_pct = float(sys.argv[4]) / 100.0
    sl_pct = float(sys.argv[5]) / 100.0
    mode = sys.argv[6] if len(sys.argv) > 6 else "realistic"
    print(f"[run] mint={mint} hhmm={hhmm} invest=${invest} TP={tp_pct*100:.2f}% SL={sl_pct*100:.2f}% mode={mode}", flush=True)

    try:
        hh, mm = [int(x) for x in hhmm.split(":")]
    except Exception:
        print("Time must be HH:MM (UTC)")
        sys.exit(1)

    try:
        net, pool = detect_network_and_pool(mint)
        candles = fetch_ohlcv_1m_last_48h(net, pool)
        if not candles:
            print("No candles in last 48h."); sys.exit(2)
        entry_ts = find_entry_minute(candles, hh, mm)
        if not entry_ts:
            print("No candle found at that HH:MM within last 48h."); sys.exit(3)
        idx = next(i for i, r in enumerate(candles) if int(r[0]) == entry_ts)
        e = candles[idx]; ts, o,h,l,c = int(e[0]), float(e[1]), float(e[2]), float(e[3]), float(e[4])
        e_dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[entry] bar @ {e_dt}  O:{o} H:{h} L:{l} C:{c}", flush=True)

        raw_entry = entry_fill(o,h,l,c, mode)
        paid_entry, buy_fee = apply_buy_costs(raw_entry, 0.03, 1.0)
        qty = invest / paid_entry
        tp_px = paid_entry * (1 + tp_pct)
        sl_px = paid_entry * (1 - sl_pct)
        print(f"[targets] TP_px={tp_px} SL_px={sl_px} (based on paid entry)", flush=True)

        exit_reason = None; exit_ts = None; exit_raw = None
        print("[walk] scanning forward bars…", flush=True)
        for r in candles[idx:]:
            ts_i, o_i,h_i,l_i,c_i = int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])
            reason = decide_exit_in_bar(o_i, h_i, l_i, tp_px, sl_px, mode, paid_entry)
            if reason:
                exit_reason = reason; exit_raw = (tp_px if reason=="TP" else sl_px); exit_ts = ts_i
                print(f"[walk] hit {reason} at ts={ts_i}", flush=True)
                break

        if not exit_reason:
            last = candles[-1]; exit_ts = int(last[0]); exit_raw = float(last[4]); exit_reason = "TIMEOUT(48h)"
            print("[walk] no hit; timeout at last bar", flush=True)

        exit_recv, sell_fee = apply_sell_costs(exit_raw, 0.03, 1.0)
        proceeds = qty * exit_recv
        pnl_usd = proceeds - invest - buy_fee - sell_fee
        ret_pct = (proceeds - invest) / invest * 100.0
        x_dt = datetime.fromtimestamp(exit_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        hold_min = (exit_ts - entry_ts) // 60

        print("\n=== RESULT ===", flush=True)
        print(f"Mint: {mint} | Net: {net} | Pool: {pool}")
        print(f"Entry @ {e_dt}  raw:{raw_entry:.8f}  paid(3%+${buy_fee:.0f}): {paid_entry:.8f}")
        print(f"Exit  @ {x_dt}  raw:{exit_raw:.8f}  recv(3%-${sell_fee:.0f}): {exit_recv:.8f}  reason:{exit_reason}")
        print(f"Qty: {qty:.8f}  Invest: {fmt_usd(invest)}  Proceeds: {fmt_usd(proceeds)}")
        print(f"PNL: {fmt_usd(pnl_usd)}   Return: {ret_pct:.2f}%   Hold: {hold_min} min", flush=True)

    except Exception as e:
        print("ERROR:", e, flush=True)
        sys.exit(9)

if __name__ == "__main__":
    main()

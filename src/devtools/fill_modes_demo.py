# src/fill_modes_demo.py  (verbose)
import sys, time
from datetime import datetime, timezone
import httpx

API_ROOT = "https://api.geckoterminal.com/api/v2"
NETWORKS = ["solana","bsc","eth","base"]  # use "eth" (not "ethereum") to match GT

def _get_json(url, params=None):
    print(f"[HTTP] GET {url}  params={params}", flush=True)
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
            js = _get_json(url, {"page": 1})
        except Exception as e:
            print(f"[detect] {net}: error {e}", flush=True)
            continue
        data = js.get("data") or []
        print(f"[detect] {net}: pools={len(data)}", flush=True)
        if data:
            addr = data[0].get("attributes", {}).get("address")
            if addr:
                print(f"[detect] -> use {net} / {addr}", flush=True)
                return net, addr
    raise RuntimeError("no pools found on solana/bsc/eth/base")

def fetch_minute_candle(network: str, pool_addr: str, hhmm: str):
    print(f"[candle] target HH:MM(UTC)={hhmm}", flush=True)
    try:
        hh, mm = [int(x) for x in hhmm.split(":")]
    except Exception:
        raise RuntimeError("Time must be HH:MM like 12:55")
    now = datetime.now(timezone.utc)
    target = datetime(now.year, now.month, now.day, hh, mm, 0, tzinfo=timezone.utc)
    if target > now:
        target = target - timedelta(days=1)
    start_ts = int(target.timestamp())
    end_ts   = start_ts + 60
    print(f"[candle] target_ts={start_ts} ({target.isoformat()})", flush=True)

    url = f"{API_ROOT}/networks/{network}/pools/{pool_addr}/ohlcv/minute"
    params = {"aggregate":1, "limit": 100, "before_timestamp": end_ts}
    js = _get_json(url, params)
    arr = (js.get("data") or {}).get("attributes", {}).get("ohlcv_list", [])

    print(f"[candle] received rows={len(arr)}; scanning for ts={start_ts}", flush=True)
    for row in arr:
        if len(row) >= 6 and int(row[0]) == start_ts:
            t,o,h,l,c,v = row
            print("[candle] FOUND", flush=True)
            return {"t":int(t),"o":float(o),"h":float(h),"l":float(l),"c":float(c),"v":float(v),
                    "dt": datetime.fromtimestamp(int(t), tz=timezone.utc)}
    raise RuntimeError("minute not found in returned batch")

def entry_fill(o,h,l,c, mode: str):
    lo, hi = float(l), float(h)
    op, cl = float(o), float(c)
    rng_up = max(0.0, hi - op)
    rng_dn = max(0.0, op - lo)
    is_green = cl >= op

    if mode == "optimistic":
        raw = op
    elif mode == "realistic":
        raw = op + (0.30 * rng_up if is_green else -0.30 * rng_dn)
    elif mode == "pessimistic":
        raw = hi
    else:
        raise RuntimeError("mode must be optimistic|realistic|pessimistic")

    raw = max(lo, min(hi, raw))
    return raw

def apply_costs(entry_price: float, slippage_pct=0.03, fee_usd=1.0):
    paid = entry_price * (1.0 + float(slippage_pct))
    return paid, float(fee_usd)

def main():
    if len(sys.argv) < 3:
        print("Usage: python src/fill_modes_demo.py <mint> <HH:MM_UTC> [mode]")
        sys.exit(1)
    mint = sys.argv[1]; hhmm = sys.argv[2]; mode = (sys.argv[3] if len(sys.argv)>3 else "realistic")
    print(f"[run] mint={mint} hhmm={hhmm} mode={mode}", flush=True)

    try:
        net, pool = detect_network_and_pool(mint)
        candle = fetch_minute_candle(net, pool, hhmm)
    except Exception as e:
        print("ERROR:", e, flush=True)
        sys.exit(2)

    o,h,l,c = candle["o"], candle["h"], candle["l"], candle["c"]
    print(f"[candle] O:{o} H:{h} L:{l} C:{c}  @ {candle['dt'].strftime('%Y-%m-%d %H:%M:%S UTC')}", flush=True)

    raw_entry = entry_fill(o,h,l,c, mode)
    paid, fee = apply_costs(raw_entry, 0.03, 1.0)
    print(f"[fill] mode={mode}  raw_entry={raw_entry}  paid(3% slip)={paid}  fee=${fee:.2f}", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    from datetime import timedelta
    main()

# src/gt_entry_from_time.py
import sys, time
from datetime import datetime, timezone, timedelta
import httpx

BASE = "https://api.geckoterminal.com/api/v2"
NETWORKS = ["solana","bsc","eth","base"]  # priority order

def get(url, params=None):
    r = httpx.get(url, params=params, headers={"accept":"application/json"}, timeout=25)
    r.raise_for_status()
    return r.json()

def find_pools_for_token(mint: str):
    for net in NETWORKS:
        url = f"{BASE}/networks/{net}/tokens/{mint}/pools"
        j = get(url, params={"include":"base_token,quote_token","page":1})
        data = j.get("data", [])
        if isinstance(data, list) and data:
            first_addr = data[0].get("attributes", {}).get("address")
            return net, first_addr
    return None, None

def fetch_ohlcv_1m_last_48h(network: str, pool: str):
    url = f"{BASE}/networks/{network}/pools/{pool}/ohlcv/minute"
    lst = []
    now = int(time.time())
    cutoff = now - 48*60*60
    before = now + 60  # small cushion
    # GeckoTerminal returns candles older than before_timestamp.
    # Paginate ~6*500 = 3000 mins (~50h) max.
    for _ in range(6):
        j = get(url, params={"aggregate":1, "limit":500, "before_timestamp": before})
        attrs = (j.get("data") or {}).get("attributes") or {}
        part = attrs.get("ohlcv_list") or []
        if not part: break
        lst.extend(part)
        # part is in ascending order. Move 'before' to the oldest ts in the batch.
        oldest_ts = int(part[0][0])
        before = oldest_ts
        if oldest_ts <= cutoff:
            break
        # be polite on rate limits
        time.sleep(0.3)
    # We accumulated from newer→older batches; ensure overall ascending by ts
    lst.sort(key=lambda r: int(r[0]))
    # Keep only last 48h
    lst = [r for r in lst if int(r[0]) >= cutoff]
    return lst

def parse_hhmm(hhmm: str):
    hh, mm = hhmm.split(":")
    return int(hh), int(mm)

def find_most_recent_minute(candles, hh:int, mm:int):
    # candles: ascending by ts; ts are minute starts
    target = None
    now = int(time.time())
    cutoff = now - 48*60*60
    for ts, *_ in candles:
        t = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        if t.minute == mm and t.hour == hh and cutoff <= int(ts) <= now:
            target = int(ts)  # we keep the latest match as we scan ascending
    return target

def main():
    if len(sys.argv) < 3:
        print("Usage: python src/gt_entry_from_time.py <mint_address> <HH:MM-UTC>")
        sys.exit(1)

    mint = sys.argv[1].strip()
    hhmm = sys.argv[2].strip()
    try:
        hh, mm = parse_hhmm(hhmm)
    except Exception:
        print("Invalid HH:MM. Example: 12:34")
        sys.exit(1)

    print(f"Mint: {mint} | Time (UTC): {hh:02d}:{mm:02d}")

    net, pool = find_pools_for_token(mint)
    if not pool:
        print("Could not find a pool for this mint in networks:", NETWORKS)
        sys.exit(2)
    print(f"Detected network: {net} | First pool: {pool}")

    candles = fetch_ohlcv_1m_last_48h(net, pool)
    if not candles:
        print("No candles in last 48h.")
        sys.exit(3)

    target_ts = find_most_recent_minute(candles, hh, mm)
    if not target_ts:
        print("No candle found at that HH:MM within last 48h.")
        # Print a nearby sample
        print(f"Newest candle UTC = {datetime.fromtimestamp(int(candles[-1][0]), tz=timezone.utc)}")
        print(f"Oldest candle UTC = {datetime.fromtimestamp(int(candles[0][0]), tz=timezone.utc)}")
        sys.exit(4)

    # locate the candle row
    row = next(r for r in candles if int(r[0]) == target_ts)
    ts_human = datetime.fromtimestamp(target_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    o,h,l,c = row[1],row[2],row[3],row[4]
    v = row[5] if len(row)>5 else None
    print("\nMATCHED CANDLE:")
    print(f"- {ts_human}  O:{o} H:{h} L:{l} C:{c} V:{v}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(9)

# src/test_gt.py
import time
import sys
from datetime import datetime, timezone
import httpx

BASE = "https://api.geckoterminal.com/api/v2"

def get(url, params=None):
    try:
        r = httpx.get(url, params=params, headers={"accept": "application/json"}, timeout=20)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300]
        print(f"HTTP ERROR: {e} | Body: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        sys.exit(1)

def main():
    network = "solana"
    pool = "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2"  # SOL/USDC (Raydium)
    url = f"{BASE}/networks/{network}/pools/{pool}/ohlcv/minute"
    params = {
        "aggregate": 1,                 # 1-minute candles
        "limit": 20,                    # last 20 candles
        "before_timestamp": int(time.time())
    }
    j = get(url, params=params)

    attrs = (j.get("data") or {}).get("attributes") or {}
    lst = attrs.get("ohlcv_list") or []

    if not isinstance(lst, list) or not lst:
        print("No candles found. Response shape:", j)
        sys.exit(2)

    print(f"OK: got {len(lst)} x 1m candles. Showing last 3 (oldest→newest):")
    for row in lst[-3:]:
        # row format: [timestamp, open, high, low, close, volume, ...]
        ts = int(row[0])
        ts_human = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        o, h, l, c = row[1], row[2], row[3], row[4]
        v = row[5] if len(row) > 5 else None
        print(f"- {ts_human}  O:{o} H:{h} L:{l} C:{c} V:{v}")

if __name__ == "__main__":
    main()

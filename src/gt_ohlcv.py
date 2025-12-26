import sys, time
from datetime import datetime, timezone
import httpx

BASE = "https://api.geckoterminal.com/api/v2"

def get(url, params=None):
    r = httpx.get(url, params=params, headers={"accept":"application/json"}, timeout=20)
    r.raise_for_status()
    return r.json()

def main():
    if len(sys.argv) < 3:
        print("Usage: python src/gt_ohlcv.py <network> <pool_address> [limit]")
        sys.exit(1)
    network = sys.argv[1]
    pool = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    url = f"{BASE}/networks/{network}/pools/{pool}/ohlcv/minute"
    params = {"aggregate": 1, "limit": limit, "before_timestamp": int(time.time())}
    j = get(url, params=params)

    attrs = (j.get("data") or {}).get("attributes") or {}
    lst = attrs.get("ohlcv_list") or []
    if not lst:
        print("No candles found. Response:", j)
        sys.exit(2)

    print(f"{network}:{pool}  ->  {len(lst)} x 1m candles (showing last 5, oldest→newest)")
    for row in lst[-5:]:
        ts = int(row[0]); o,h,l,c = row[1],row[2],row[3],row[4]
        v = row[5] if len(row)>5 else None
        tstr = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"- {tstr}  O:{o} H:{h} L:{l} C:{c} V:{v}")
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(3)

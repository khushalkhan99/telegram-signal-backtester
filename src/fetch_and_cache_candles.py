import os, json, csv, argparse, datetime as dt, urllib.request
from pathlib import Path

# --- .env loader ---
def _load_dotenv():
    for candidate in [Path(__file__).resolve().parent.parent / ".env", Path(__file__).resolve().parent / ".env"]:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k,v = line.strip().split("=",1)
                        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
_load_dotenv()

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent":"Mozilla/5.0 (Backtester)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

# --- step 1: find top pool for token ---
def get_top_pool(network, token):
    base = "https://api.geckoterminal.com/api/v2"
    url = f"{base}/networks/{network}/tokens/{token}/pools"
    data = http_get(url)
    pools = data.get("data") or []
    if not pools:
        raise RuntimeError(f"No pools found for {token} on {network}")
    chosen = pools[0]
    attrs = chosen.get("attributes") or {}
    return attrs.get("address") or chosen.get("id")

# --- step 2: fetch OHLCV from pool with smart caching ---
def fetch_gt_candles(network, pool, start_unix=None, signal_unix=None):
    base = "https://api.geckoterminal.com/api/v2"
    now_unix = int(dt.datetime.now(dt.timezone.utc).timestamp())
    results = []
    before = now_unix

    # Smart caching: if signal_unix provided, cache around signal time
    if signal_unix:
        # Cache 30 minutes after signal time only (no before data needed)
        cache_start = signal_unix  # Start exactly at signal time
        cache_end = signal_unix + (30 * 60)   # 30 minutes after
    else:
        # Default: cache last 48 hours
        cache_start = now_unix - (48 * 3600)
        cache_end = now_unix

    while True:
        url = f"{base}/networks/{network}/pools/{pool}/ohlcv/minute?aggregate=1&before_timestamp={before}&limit=100"
        data = http_get(url)
        ohlcv = (data.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or [])
        if not ohlcv:
            break

        chunk = [{"ts": r[0], "o": r[1], "h": r[2], "l": r[3], "c": r[4], "v": r[5]} for r in ohlcv]
        results.extend(chunk)

        before = chunk[-1]["ts"] - 60
        if before <= cache_start:
            break

    # Filter to cache window
    results = [c for c in results if cache_start <= c["ts"] <= cache_end]
    
    # Keep only candles after start_unix if given
    if start_unix:
        results = [c for c in results if c["ts"] >= start_unix]

    # results are newest→oldest, reverse them
    results.reverse()
    return results



def fetch_be_price(chain, token):
    key = os.getenv("BIRDEYE_API_KEY") or os.getenv("TB_BIRDEYE_KEY") or os.getenv("BIRDEYE_KEY")
    if not key: return None
    url = f"https://public-api.birdeye.so/defi/price?address={token}"
    headers = {"x-chain":chain,"X-API-KEY":key}
    try:
        data = http_get(url, headers=headers)
        return data.get("data",{}).get("value")
    except Exception:
        return None

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--chain", choices=["SOL","ETH","BNB"], required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--time", required=True, help="Call time PKT HH:MM (last 24h)")
    args = p.parse_args()

    PKT = dt.timezone(dt.timedelta(hours=5))
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_pkt = now_utc.astimezone(PKT)
    hh, mm = map(int, args.time.split(":"))
    cand_pkt = now_pkt.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand_pkt > now_pkt:
        cand_pkt -= dt.timedelta(days=1)
    cand_utc = cand_pkt.astimezone(dt.timezone.utc)
    t_unix = int(cand_utc.timestamp())

    net_map = {"SOL":"solana","ETH":"eth","BNB":"bsc"}
    gt_network = net_map[args.chain]

    pool = get_top_pool(gt_network, args.token)
    candles = fetch_gt_candles(gt_network, pool)

    exact = [c for c in candles if c["ts"] == t_unix]
    be_price = fetch_be_price(gt_network, args.token)

    print(f"== {args.chain} {args.token} ==")
    print(f"Call time: {cand_pkt} PKT ({cand_utc} UTC) unix={t_unix}")
    print(f"GT pool: {pool} candles={len(candles)} exact={'yes' if exact else 'no'}")
    if be_price: print(f"Birdeye spot price ≈ {be_price}")
    else: print("Birdeye price not available")

    outdir = Path(__file__).resolve().parent.parent / "out"
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"{args.chain}_{args.token[:6]}_{cand_pkt.strftime('%Y%m%d')}.csv"
    with open(outfile,"w",newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts","o","h","l","c","v"])
        w.writeheader()
        for r in candles: w.writerow(r)
    print(f"Saved {len(candles)} candles -> {outfile}")

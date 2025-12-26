import os
from pathlib import Path

# --- auto-load .env manually ---
def _load_dotenv():
    for candidate in [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env"
    ]:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k,v = line.strip().split("=",1)
                        os.environ.setdefault(k, v.strip().strip('"').strip("'"))

_load_dotenv()

import os
from pathlib import Path

# --- auto-load .env manually ---
def _load_dotenv():
    for candidate in [Path(__file__).resolve().parent.parent / ".env", Path(__file__).resolve().parent / ".env"]:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k,v = line.strip().split("=",1)
                        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
_load_dotenv()
import os, sys, time, json, math, argparse, datetime as dt
import urllib.request, urllib.parse

# ---- Helpers ---------------------------------------------------------------
PKT = dt.timezone(dt.timedelta(hours=5))
NET_MAP_BIRDEYE = {"SOL":"solana","ETH":"ethereum","BNB":"bsc"}
NET_MAP_GT = {"SOL":"solana","ETH":"eth","BNB":"bsc"}

def read_env_var_from_dotenv(keys, dotenv_path=".env"):
    # Try OS env first, then a simple .env parser
    for k in keys:
        if os.getenv(k): return os.getenv(k)
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k,v = line.strip().split("=",1)
                    if k in keys: return v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None

def http_get(url, headers=None):
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Backtester Probe Script)"
    }
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def pick_top_pool_for_token_gt(network_gt, token_address):
    # GeckoTerminal: GET /api/v2/networks/{network}/tokens/{token}/pools
    base = "https://api.geckoterminal.com/api/v2"
    url = f"{base}/networks/{network_gt}/tokens/{token_address}/pools"
    data = http_get(url)
    pools = data.get("data") or []
    if not pools:
        return None, {"reason":"no pools returned"}
    # Heuristic: first item is already "top" in GT; otherwise choose by reserve/volume if present
    chosen = pools[0]
    # Some responses keep pool address under attributes or id
    attrs = (chosen.get("attributes") or {})
    pool_addr = attrs.get("address") or chosen.get("id") or attrs.get("pool_address")
    if not pool_addr:
        return None, {"reason":"pool address missing in response"}
    return pool_addr, {"pool_count": len(pools)}

def fetch_ohlcv_gt_minute(network_gt, pool_addr, t_unix, window_sec=600):
    # Pull a small window ending just after target (use before_timestamp)
    base = "https://api.geckoterminal.com/api/v2"
    before = int(t_unix + 60)  # include the target minute
    url = (f"{base}/networks/{network_gt}/pools/{pool_addr}/ohlcv/minute"
           f"?aggregate=1&before_timestamp={before}&limit=100")
    data = http_get(url)
    ohlcv = (((data.get("data") or {}).get("attributes") or {}).get("ohlcv_list")) or []
    # ohlcv rows: [ts, o, h, l, c, v]
    return [{"ts":r[0], "o":r[1], "h":r[2], "l":r[3], "c":r[4], "v":r[5]} for r in ohlcv]

def fetch_ohlcv_birdeye(chain_be, token_address, t_unix, window_sec=600, api_key=None):
    # Birdeye V3 token OHLCV: /defi/v3/ohlcv?address=...&type=1m&time_from=&time_to=
    start = int(t_unix - window_sec//2)
    end   = int(t_unix + window_sec//2)
    params = urllib.parse.urlencode({
        "address": token_address,
        "type": "1m",
        "time_from": start,
        "time_to": end
    })
    url = f"https://public-api.birdeye.so/defi/v3/ohlcv?{params}"
    headers = {
        "x-chain": chain_be,
        "accept": "application/json",
    }
    if api_key:
        headers["X-API-KEY"] = api_key
    data = http_get(url, headers=headers)
    # V3 usually returns {"data":{"items":[{"t":..,"o":..,"h":..,"l":..,"c":..,"v":..}, ...]}}
    items = ((data.get("data") or {}).get("items")) or []
    out = []
    for it in items:
        ts = it.get("t") or it.get("unixTime") or it.get("time") or it.get("timestamp")
        if ts is None: continue
        out.append({"ts": int(ts), "o": it.get("o"), "h": it.get("h"), "l": it.get("l"), "c": it.get("c"), "v": it.get("v")})
    return out

def nearest_candle(items, target_unix):
    if not items: return None
    best = min(items, key=lambda x: abs(x["ts"] - target_unix))
    return {"exists_exact": any(x["ts"]==target_unix for x in items),
            "nearest_ts": best["ts"],
            "delta_s": int(best["ts"] - target_unix)}

# ---- CLI -------------------------------------------------------------------
p = argparse.ArgumentParser(description="Probe Birdeye + GeckoTerminal 1m candles for a token @ minute")
p.add_argument("--chain", required=True, choices=["SOL","ETH","BNB"], help="Network: SOL/ETH/BNB")
p.add_argument("--token", required=True, help="Mint/contract address of the token")
p.add_argument("--time",  required=True, help='Pakistan time HH:MM for the last 24h (e.g., "23:57")')
args = p.parse_args()

# Resolve target minute (PKT -> UTC -> unix at start-of-minute)
now_utc = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
now_pkt = now_utc.astimezone(PKT)
hh, mm = map(int, args.time.split(":"))
cand_pkt = now_pkt.replace(hour=hh, minute=mm, second=0, microsecond=0)
if cand_pkt > now_pkt:
    cand_pkt -= dt.timedelta(days=1)
cand_utc = cand_pkt.astimezone(dt.timezone.utc)
t_unix = int(cand_utc.timestamp())

# Env key
be_key = read_env_var_from_dotenv(["TB_BIRDEYE_KEY","BIRDEYE_API_KEY","BIRDEYE_KEY"])

print(f"== Probe @ {cand_pkt.strftime('%Y-%m-%d %H:%M PKT')}  ({cand_utc.strftime('%Y-%m-%d %H:%M UTC')})  unix={t_unix}")
print(f"Chain: {args.chain}  Token: {args.token}")
print("-"*78)

# Birdeye
chain_be = NET_MAP_BIRDEYE[args.chain]
be_items = []
be_err = None
try:
    be_items = fetch_ohlcv_birdeye(chain_be, args.token, t_unix, api_key=be_key)
    be_near = nearest_candle(be_items, t_unix)
    print(f"[Birdeye] items={len(be_items)}  exact={bool(be_near and be_near['exists_exact'])}  "
          f"nearest_delta={None if not be_near else be_near['delta_s']}")
except Exception as e:
    be_err = str(e)
    print(f"[Birdeye] ERROR: {be_err}")

# GeckoTerminal
network_gt = NET_MAP_GT[args.chain]
gt_items = []
gt_err = None
pool_addr = None
try:
    pool_addr, meta = pick_top_pool_for_token_gt(network_gt, args.token)
    if not pool_addr:
        raise RuntimeError(f"no pool: {meta}")
    gt_items = fetch_ohlcv_gt_minute(network_gt, pool_addr, t_unix)
    gt_near = nearest_candle(gt_items, t_unix)
    print(f"[GeckoTerminal] pool={pool_addr} items={len(gt_items)}  exact={bool(gt_near and gt_near['exists_exact'])}  "
          f"nearest_delta={None if not gt_near else gt_near['delta_s']}")
except Exception as e:
    gt_err = str(e)
    print(f"[GeckoTerminal] ERROR: {gt_err}")

# DexScreener (informational)
print("[DexScreener] No official OHLCV endpoint; skipping candles check.")

# Quick JSON dump (optional)
out = {
    "input": {"chain":args.chain, "token":args.token, "pkt_time":args.time, "unix":t_unix},
    "birdeye": {"count":len(be_items), "error":be_err},
    "geckoterminal": {"count":len(gt_items), "pool":pool_addr, "error":gt_err}
}
print("-"*78)
print(json.dumps(out, indent=2))

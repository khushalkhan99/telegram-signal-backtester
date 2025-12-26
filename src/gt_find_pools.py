# src/gt_find_pools.py
import sys, httpx, json

BASE = "https://api.geckoterminal.com/api/v2"
NETWORKS = ["solana", "bsc", "eth", "base"]  # try in this priority

def get(url, params=None):
    r = httpx.get(url, params=params, headers={"accept": "application/json"}, timeout=20)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print("HTTP ERROR:", e, "| Body:", r.text[:240])
        return None
    try:
        return r.json()
    except Exception:
        print("Non-JSON:", r.text[:240])
        return None

def find_pools_for_token(mint: str):
    for net in NETWORKS:
        url = f"{BASE}/networks/{net}/tokens/{mint}/pools"
        j = get(url, params={"include":"base_token,quote_token","page":1})
        if not j or "data" not in j: 
            continue
        data = j["data"]
        if isinstance(data, list) and len(data) > 0:
            return net, data, j.get("included", [])
    return None, [], []

def pretty_token(included, rel_key):
    # find token record by relationship id
    # included contains base_token/quote_token with 'type': 'tokens'
    if not included or not rel_key: 
        return "?"
    target_id = rel_key.get("data", {}).get("id")
    for item in included:
        if item.get("id") == target_id:
            a = item.get("attributes", {})
            sym = a.get("symbol") or a.get("name") or "?"
            return sym
    return "?"

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/gt_find_pools.py <mint_address>")
        sys.exit(1)
    mint = sys.argv[1].strip()
    net, pools, included = find_pools_for_token(mint)
    if not pools:
        print("No pools found for:", mint)
        sys.exit(2)

    print(f"Network detected: {net}")
    print(f"Top {min(5,len(pools))} pools for token {mint}:")
    for p in pools[:5]:
        attr = p.get("attributes", {})
        rel = p.get("relationships", {})
        base_sym = pretty_token(included, rel.get("base_token"))
        quote_sym = pretty_token(included, rel.get("quote_token"))
        addr = attr.get("address")
        dex = attr.get("dex")
        liq = attr.get("reserve_in_usd")
        vol24 = attr.get("volume_usd")
        print(f"- {addr} | {base_sym}/{quote_sym} | DEX:{dex} | Liquidity:${liq} | Vol24h:${vol24}")

    # also print the first pool address alone (so we can feed it to OHLCV next step)
    first = pools[0].get("attributes", {}).get("address")
    print("\nFIRST_POOL_ADDRESS:", first)
    print("FIRST_NETWORK:", net)

if __name__ == "__main__":
    main()

# src/test_api.py
import os, sys, time
from dotenv import load_dotenv
import httpx

load_dotenv()
API_KEY = os.getenv("BIRDEYE_API_KEY")
if not API_KEY:
    print("ERROR: Missing BIRDEYE_API_KEY in .env")
    sys.exit(1)

BASE_URL = "https://public-api.birdeye.so"

def fetch_ohlcv_1m_solana():
    headers = {
        "accept": "application/json",
        "X-API-KEY": API_KEY,
        "x-chain": "solana",
    }
    now = int(time.time())
    params = {
        "address": "So11111111111111111111111111111111111111112",  # WSOL
        "type": "1m",                   # legacy OHLCV supports 1m+ on free plan
        "time_from": now - 3600,        # last 60 minutes
        "time_to": now,
        "limit": 5000,
    }
    r = httpx.get(f"{BASE_URL}/defi/ohlcv", headers=headers, params=params, timeout=30)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        print("HTTP ERROR:", e, "| Body:", r.text[:300])
        sys.exit(2)

    j = r.json()
    data = j["data"] if isinstance(j, dict) and "data" in j else j
    if not isinstance(data, list):
        print("Unexpected JSON shape:", j)
        sys.exit(3)

    print(f"OK: fetched {len(data)} x 1m candles (showing first 2 rows):")
    for row in data[:2]:
        print(row)

if __name__ == "__main__":
    fetch_ohlcv_1m_solana()

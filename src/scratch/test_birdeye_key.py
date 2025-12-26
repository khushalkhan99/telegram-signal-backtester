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

import os, json, urllib.request

API_KEY = os.getenv("BIRDEYE_API_KEY") or os.getenv("TB_BIRDEYE_KEY") or os.getenv("BIRDEYE_KEY")
if not API_KEY:
    print("❌ No API key loaded from env")
    exit(1)

url = "https://public-api.birdeye.so/defi/price?address=So11111111111111111111111111111111111111112"
headers = {
    "accept": "application/json",
    "x-chain": "solana",
    "X-API-KEY": API_KEY
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print("✅ Birdeye response:", r.read().decode()[:200])
except Exception as e:
    print("❌ Error:", e)

# src/mc_parse_test.py
import re, sys

MULTS = {"":1,"k":1_000,"m":1_000_000,"b":1_000_000_000,"t":1_000_000_000_000}

def parse_mc(s: str) -> float:
    if s is None:
        raise ValueError("empty")
    raw = s.strip().lower().replace(",", "").replace("$","")
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([kmbt]?)\s*", raw)
    if not m:
        raise ValueError(f"cannot parse: {s!r}")
    num = float(m.group(1)); suf = m.group(2) or ""
    return num * MULTS.get(suf, 1)

def fmt_usd(x: float) -> str:
    return f"${x:,.2f}"

def main():
    cases = sys.argv[1:] or ["33.12k","108.1k","1.23m","12.34M","2.5B","$7.5k","987","1,234,567"]
    for c in cases:
        try:
            val = parse_mc(c)
            print(f"{c:>10} -> {fmt_usd(val)}")
        except Exception as e:
            print(f"{c:>10} -> ERROR: {e}")

if __name__ == "__main__":
    main()

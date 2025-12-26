import io, os, re

PATH = os.path.join("src", "single_trade_sim_partial_mc.py")

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

orig = src

# 1) Unescape any accidental backslashed triple quotes
src = src.replace('\\"\"\"', '"""').replace('\\\"\\\"\\\"', '"""').replace('\\"""', '"""')

# 2) Ensure our env-based helpers exist (insert or replace the old apply_* helpers)
helpers_pat = re.compile(
    r"def\s+apply_buy_costs\([^\)]*\):[^\n]*\n\s*def\s+apply_sell_costs\([^\)]*\):[^\n]*\n",
    re.DOTALL
)

helpers_block = '''
import os

def _cfg():
    slip = float(os.getenv("TB_SLIP", "0"))
    slip_mode = os.getenv("TB_SLIP_MODE", "amount")      # 'price' | 'amount'
    slip_side = os.getenv("TB_SLIP_SIDE", "sell")        # 'both' | 'buy' | 'sell'
    buy_fee = float(os.getenv("TB_BUY_FEE", "0.01"))     # fraction
    sell_fee = float(os.getenv("TB_SELL_FEE", "0.01"))   # fraction
    return slip, slip_mode, slip_side, buy_fee, sell_fee

def execute_buy(raw_price, invest_usd, buy_fee, slip, slip_mode, slip_side):
    """Return qty, paid_entry_px, buy_fee_usd, log_str"""
    buy_fee_usd = invest_usd * buy_fee
    cash_after_fee = invest_usd - buy_fee_usd
    if slip_side in ("both","buy"):
        if slip_mode == "price":
            paid_entry_px = raw_price * (1 + slip)
            qty = cash_after_fee / paid_entry_px
            log = f"raw:{raw_price:.8f}  paid(price,{int(slip*100)}%+fee): {paid_entry_px:.8f}  qty:{qty:.8f}"
            return qty, paid_entry_px, buy_fee_usd, log
        else:  # amount
            eff_cash = cash_after_fee * (1 - slip)
            qty = eff_cash / raw_price
            log = f"raw:{raw_price:.8f}  paid(amount,{int(slip*100)}%+fee) cash:{eff_cash:.2f}  qty:{qty:.8f}"
            return qty, raw_price, buy_fee_usd, log
    # no slippage on buy
    qty = cash_after_fee / raw_price
    log = f"raw:{raw_price:.8f}  paid(fee only): {raw_price:.8f}  qty:{qty:.8f}"
    return qty, raw_price, buy_fee_usd, log

def execute_sell_fill(raw_price, sub_qty, sell_fee, slip, slip_mode, slip_side, tstr, reason, frac):
    """Return sub_proceeds, sub_sell_fee_usd, log_line"""
    sub_gross = sub_qty * raw_price
    sub_sell_fee = sub_gross * sell_fee
    after_fee = sub_gross - sub_sell_fee

    if slip_side in ("both","sell"):
        if slip_mode == "price":
            recv_px = raw_price * (1 - slip)
            sub_proceeds = sub_qty * recv_px * (1 - sell_fee)
            log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(price,{int(slip*100)}%):{recv_px:.8f}  part:{frac*100:.1f}%"
            return sub_proceeds, sub_sell_fee, log
        else:  # amount
            sub_proceeds = after_fee * (1 - slip)
            log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(amount,{int(slip*100)}%)  part:{frac*100:.1f}%"
            return sub_proceeds, sub_sell_fee, log
    # no slippage on sell
    sub_proceeds = after_fee
    log = f"- Exit {reason:<14} @ {tstr}  raw:{raw_price:.8f}  recv(no slip)  part:{frac*100:.1f}%"
    return sub_proceeds, sub_sell_fee, log
'''.lstrip()

if helpers_pat.search(src):
    src = helpers_pat.sub(helpers_block, src)
else:
    # If not found (already patched once), ensure helpers exist near the top.
    insert_at = src.find("\n", 0) + 1
    src = src[:insert_at] + helpers_block + src[insert_at:]

# 3) Replace the BUY leg usage + entry print
buy_pat = re.compile(
    r"paid_entry,\s*buy_fee\s*=\s*apply_buy_costs\([^\n]+\)\s*\n\s*qty\s*=\s*invest\s*/\s*paid_entry\s*[\s\S]*?print\(\s*f\"Entry\s*@\s*\{e_dt\}[^\n]+\"\s*\)",
    re.DOTALL
)
buy_block = '''
slip, slip_mode, slip_side, buy_fee_frac, sell_fee_frac = _cfg()
qty, paid_entry, buy_fee_usd, buy_log = execute_buy(raw_entry, invest, buy_fee_frac, slip, slip_mode, slip_side)
print(f"Entry @ {e_dt}  {buy_log}  buy_fee:${buy_fee_usd:.2f} [{how}]")
'''.lstrip()
src = buy_pat.sub(buy_block, src)

# 4) Replace the SELL loop + proceeds/pnl prints
sell_pat = re.compile(
    r"proceeds\s*=\s*0\.0;\s*sell_fee_total\s*=\s*0\.0[\s\S]*?for\s*\([^)]+\)\s*in\s*fills:\s*\n\s*sub_qty\s*=\s*qty\s*\*\s*frac\s*\n\s*proceeds\s*\+=\s*sub_qty\s*\*\s*recv_px\s*\n\s*sell_fee_total\s*\+=\s*1\.0[\s\S]*?print\(\s*f\"Proceeds:[^\n]+\"\s*\)\s*\n\s*print\(\s*f\"PNL:[^\n]+\"\s*\)",
    re.DOTALL
)
sell_block = '''
proceeds = 0.0
sell_fee_total = 0.0

for (tstr, raw_px, frac, reason) in fills:
    sub_qty = qty * frac
    sub_proceeds, sub_sell_fee, log_line = execute_sell_fill(raw_px, sub_qty, sell_fee_frac, slip, slip_mode, slip_side, tstr, reason, frac)
    proceeds += sub_proceeds
    sell_fee_total += sub_sell_fee
    print(log_line)

pnl_usd = proceeds - invest - buy_fee_usd
ret_pct = (pnl_usd / invest) * 100.0

print(f"Proceeds: ${proceeds:,.2f}  | Buy fee: ${buy_fee_usd:.2f}  | Sell fee total: ${sell_fee_total:,.2f}")
print(f"PNL: ${pnl_usd:,.2f}   Return: {ret_pct:.2f}%")
'''.lstrip()
src = sell_pat.sub(sell_block, src)

changed = (src != orig)
with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(src)

print("Patched." if changed else "No changes (already patched).")

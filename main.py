import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_list(value):
    
    if pd.isna(value) or str(value).strip() == "":
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]


def parse_holdings(value):
    
    holdings = []
    for item in parse_list(value):
        sec, qty, price = item.split(":")
        holdings.append((sec.strip(), float(qty), float(price)))
    return holdings


def load_portfolios(path):
    df = pd.read_csv(path, dtype=str)
    portfolios = {}
    for _, row in df.iterrows():
        portfolios[row["portfolio_id"].strip()] = {
            "cash_balance": float(row["cash_balance"]),
            "restricted_securities": parse_list(row["restricted_securities"]),
            "max_position_pct": float(row["max_position_pct"]),
            "current_holdings": parse_holdings(row["current_holdings"]),
        }
    return portfolios


def check_trade(trade, pf):
    # Step 1: validate
    try:
        qty = float(trade["quantity"])
        price = float(trade["price"])
    except (ValueError, TypeError):
        return "Rejected", "Invalid trade data."
    action = str(trade["action"]).strip().title()
    if not (qty > 0 and price > 0) or action not in ("Buy", "Sell"):
        return "Rejected", "Invalid trade data."

    sec = str(trade["security_id"]).strip()

    # Step 2: restricted security
    if sec in pf["restricted_securities"]:
        return "Rejected", "Security is restricted for this portfolio."

    held_qty = sum(q for s, q, p in pf["current_holdings"] if s == sec)

    # Step 3: sell check
    if action == "Sell":
        if held_qty < qty:
            return "Rejected", "Insufficient holdings to sell."
        return "Approved", "All checks passed."

    # Step 4: buy affordability
    cost = qty * price
    if cost > pf["cash_balance"]:
        return "Rejected", "Insufficient cash for this buy order."

    # Step 5: concentration check
    post_cash = pf["cash_balance"] - cost
    this_value = (held_qty + qty) * price
    other_value = sum(q * p for s, q, p in pf["current_holdings"] if s != sec)
    total_after = post_cash + this_value + other_value
    position_pct = this_value / total_after
    if position_pct > pf["max_position_pct"]:
        return "Needs Manual Sign-off", "Exceeds maximum position concentration — requires approval."

    # Step 6
    return "Approved", "All checks passed."


# ---------- Main ----------
portfolios = load_portfolios(os.path.join(BASE_DIR, "portfolio_reference.csv"))
trades = pd.read_csv(os.path.join(BASE_DIR, "trades_test.csv"))

results = []
for _, row in trades.iterrows():
    pf = portfolios.get(str(row["portfolio_id"]).strip())
    if pf is None:
        results.append(("Rejected", "Unknown portfolio."))
    else:
        results.append(check_trade(row, pf))

trades["decision"] = [r[0] for r in results]
trades["reason"] = [r[1] for r in results]

trades.to_csv(os.path.join(BASE_DIR, "trade_decisions.csv"), index=False)
print(trades.to_string(
    index=False,
    formatters={
        "decision": lambda x: f"{x:<22}",
        "reason": lambda x: f"{x:<65}",
    },
))
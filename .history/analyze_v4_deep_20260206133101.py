"""Investigate why 10 parameter variations produce identical results,
and check if the Nov 20, 2025 split causes problems during the backtest."""
import csv
import json

results_file = r"c:\Users\anand\Documents\trading_plan\backtest\trend_filter_results_1.csv"

with open(results_file) as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# ========== IDENTICAL RESULTS INVESTIGATION ==========
print("=" * 80)
print("WHY ARE 10 BACKTESTS PRODUCING IDENTICAL RESULTS?")
print("=" * 80)
print()

# These params changed but produced the EXACT same results as baseline:
# entry_zscore=1.4, entry_zscore=1.6, warmup_days=160,
# max_drawdown_pct=0.15, max_drawdown_pct=0.2,
# dd_position_scale=0.3, dd_position_scale=0.7,
# vol_scaling=True, entry_zscore=1.4+max_dd=0.2

print("Parameters that had NO EFFECT (identical to baseline):")
print("-" * 80)
print()

print("1. entry_zscore=1.4 AND entry_zscore=1.6 → SAME as entry_zscore=1.5")
print("   This means the actual Z-scores during the backtest period are")
print("   always > 1.6 or < 1.4 when entries happen, so changing the")
print("   threshold between 1.4-1.6 catches the SAME set of trades.")
print()

print("2. max_drawdown_pct=0.15, 0.20, 0.25 → ALL SAME")
print("   IMPLICATION: Drawdown NEVER reached 15%! The drawdown mode")
print("   never activated, so changing the threshold changes nothing.")
print("   Actual max DD was 13.5%, so 15%/20%/25% all have the same effect.")
print()

print("3. dd_position_scale=0.3 AND dd_position_scale=0.7 → SAME as 0.5")
print("   CONFIRMS drawdown mode never activates (since DD<15%).")
print()

print("4. vol_scaling=True → SAME as vol_scaling=False")
print("   The ATR thresholds (high=30, med=20) are never breached!")
print("   QQQ daily ATR as % of price is ~1-2%, never reaching 20%+.")
print("   The vol scaling feature is completely inert.")
print()

print("5. warmup_days=160 → SAME as warmup_days=210")
print("   The SMA 20/50 only needs 50 days to warm up.")
print("   Both 160 and 210 are sufficient; reducing to 60 changes the")
print("   trading start date but SMA values would already be ready.")
print()

# ========== THE REAL NUMBERS ==========
print("\n" + "=" * 80)
print("THE FUNDAMENTAL PROBLEM: RAZOR-THIN EDGE")
print("=" * 80)
print()

# Baseline stats
baseline = None
for r in rows:
    params = json.loads(r['ParametersJson'])
    if params.get('_hash') == 'f67fc4ba14b1':
        baseline = r
        break

if baseline:
    trades = int(baseline['TotalTrades'])
    profit = float(baseline['TotalProfit'])
    loss = float(baseline['TotalLoss'])
    net = profit + loss
    win_rate = float(baseline['WinRate'])
    avg_win = float(baseline['AverageWin'])
    avg_loss = float(baseline['AverageLoss'])
    
    # Expected value per trade
    ev = win_rate * avg_win - (1 - win_rate) * avg_loss
    
    print(f"Baseline (1-year, Jan 2025 → Jan 2026):")
    print(f"  Total trades: {trades}")
    print(f"  Win rate: {win_rate:.1%}")
    print(f"  Average winning trade: ${avg_win:.0f}")
    print(f"  Average losing trade: ${avg_loss:.0f}")
    print(f"  Win/Loss ratio: {avg_win/avg_loss:.2f}")
    print(f"  Expected value per trade: ${ev:.2f}")
    print(f"  Net P&L over {trades} trades: ${net:,.0f}")
    print()
    print(f"  THE PROBLEM:")
    print(f"  ────────────")
    print(f"  Win rate is decent (62.9%) but avg winner ($236) is much")
    print(f"  smaller than avg loser ($387). Win/loss ratio = 0.61.")
    print(f"  For a 62.9% win rate to be profitable, you need")
    print(f"  Win/Loss ratio > (1-WR)/WR = {(1-win_rate)/win_rate:.2f}")
    print(f"  You have: {avg_win/avg_loss:.2f}. Barely above breakeven.")
    print()
    print(f"  Net edge per trade: ${net/trades:.2f}")
    print(f"  That's $4.50 per trade on a $57,000 position = 0.008%.")
    print(f"  After real-world slippage and commissions, this is ZERO.")

# ========== WHY ARE WINNERS SO SMALL? ==========
print()
print("=" * 80)
print("WHY ARE WINNERS SO SMALL FOR 3X LEVERAGED ETFS?")
print("=" * 80)
print()
print("The algorithm uses a 2% STOP LOSS. On a $57,000 position:")
print(f"  2% stop = ${57000*0.02:,.0f} max loss")
print(f"  But avg loss = $387, meaning most losses are much smaller")
print(f"  (Z-score normalization exits or EOD close often exit earlier)")
print()
print("The EXIT is when Z-score normalizes back to ±0.32.")
print("Mean reversion on 5-min bars means tiny moves back to mean.")
print("Z-score goes from -1.5 to -0.32 = small price movement.")
print()
print("KEY ISSUE: The strategy is scalping tiny Z-score oscillations")
print("on 5-minute bars. The 3x leverage amplifies BOTH the signal")
print("AND the noise. The stop loss at 2% cuts winners AND losers short.")
print()
print("With stop_loss=2.5% or 3%: Return becomes NEGATIVE (-6.4%, -6.6%)")
print("This means the 2% stop is preventing larger losses, but also")
print("proving that without tight stops, the strategy bleeds money.")
print()
print("=" * 80)
print("STRUCTURAL ISSUES")
print("=" * 80)
print()
print("1. ASYMMETRIC WIN/LOSS: Winners avg $236, losers avg $387")
print("   This is classic mean-reversion: you exit at mean (small gain)")
print("   but get stopped out on outliers (large loss).")
print()
print("2. NO PROFIT TARGETS: The only profit exit is Z-score normalization.")
print("   There's no trailing stop or profit target to capture big moves.")
print()
print("3. SCALPING 3X ETFs: 3x leverage means 3x spread, 3x slippage,")
print("   3x overnight decay. Scalping tiny moves on these is expensive.")
print()
print("4. RATIO-BASED Z-SCORE: The TQQQ/SQQQ ratio changes dramatically")
print("   at every split. The Z-score lookback (46 bars = ~4 hours) is")
print("   short enough to recover, but post-split ratio levels are")
print("   completely different from pre-split, making the Z-score")
print("   unreliable near split dates.")
print()
print("5. ENTRIES ARE TOO AGGRESSIVE: 4.2 trades/day with $4.50 edge/trade")
print("   = ~$19/day. This barely covers commissions on Alpaca.")

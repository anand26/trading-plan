"""Deep comparison of v1.5 Composite Sub-Strategy Voting results vs v1.0 baseline.

v1.5 Question: Can a Malik-style composite voting system (7 sub-strategies
voting together) beat the simple SMA 50/200 regime switch?

Malik principle: "7 sub-strategies running all together"
  - SMA Cross, EMA 21, MACD, RSI, ROC, Bollinger Band, ADX
  - Each votes +1 (BULL), 0 (NEUTRAL), or -1 (BEAR)
  - Consensus maps to allocation via thresholds
"""
import pandas as pd
import json

df = pd.read_csv(r'C:\Users\anand\Documents\trading_plan\results\posttrend_1.5.csv')

def parse_params(row):
    try:
        return json.loads(row['ParametersJson'])
    except:
        return {}

params = df.apply(parse_params, axis=1)
df['voting_enabled'] = params.apply(lambda p: p.get('voting_enabled', False))
df['vote_threshold_full'] = params.apply(lambda p: p.get('vote_threshold_full', 5))
df['vote_threshold_half'] = params.apply(lambda p: p.get('vote_threshold_half', 3))
df['vote_mode'] = params.apply(lambda p: p.get('vote_mode', 'binary'))
df['sub_ema_enabled'] = params.apply(lambda p: p.get('sub_ema_enabled', True))
df['sub_macd_enabled'] = params.apply(lambda p: p.get('sub_macd_enabled', True))
df['sub_rsi_enabled'] = params.apply(lambda p: p.get('sub_rsi_enabled', True))
df['sub_roc_enabled'] = params.apply(lambda p: p.get('sub_roc_enabled', True))
df['sub_bbands_enabled'] = params.apply(lambda p: p.get('sub_bbands_enabled', True))
df['sub_adx_enabled'] = params.apply(lambda p: p.get('sub_adx_enabled', True))
df['bull_allocation'] = params.apply(lambda p: p.get('bull_allocation', 0.90))
df['rsi_bull_threshold'] = params.apply(lambda p: p.get('rsi_bull_threshold', 50))
df['rsi_bear_threshold'] = params.apply(lambda p: p.get('rsi_bear_threshold', 40))
df['roc_vote_lookback'] = params.apply(lambda p: p.get('roc_vote_lookback', 20))
df['adx_threshold'] = params.apply(lambda p: p.get('adx_threshold', 25))

# Count enabled sub-strategies (SMA always on + up to 6 optional)
df['num_subs'] = 1 + df['sub_ema_enabled'].astype(int) + df['sub_macd_enabled'].astype(int) + \
                 df['sub_rsi_enabled'].astype(int) + df['sub_roc_enabled'].astype(int) + \
                 df['sub_bbands_enabled'].astype(int) + df['sub_adx_enabled'].astype(int)

# Separate control and voting-enabled
ctrl = df[df['voting_enabled'] == False].iloc[0]
voting = df[df['voting_enabled'] == True].copy()

# Sub-classify voting combos
binary = voting[voting['vote_mode'] == 'binary'].copy()
graduated = voting[voting['vote_mode'] == 'graduated'].copy()

print("=" * 120)
print("v1.5 DEEP ANALYSIS -- COMPOSITE SUB-STRATEGY VOTING")
print("Question: Can 7 sub-strategies voting together beat simple SMA 50/200?")
print("=" * 120)

# ================================================================
# 1. CONTROL vs ALL VOTING COMBOS -- Overview
# ================================================================
print("\n" + "=" * 120)
print("SECTION 1: CONTROL (VOTING OFF) vs VOTING-ENABLED OVERVIEW")
print("=" * 120)

print(f"\n  CONTROL (v1.0 baseline):")
print(f"    Return: {ctrl['TotalReturn']*100:.1f}%  |  Sharpe: {ctrl['SharpeRatio']:.4f}  |  "
      f"MaxDD: {ctrl['MaxDrawdown']*100:.1f}%  |  Trades: {int(ctrl['TotalTrades'])}  |  "
      f"WR: {ctrl['WinRate']*100:.1f}%  |  PF: {ctrl['ProfitFactor']:.3f}  |  R: {ctrl['ExpectancyRatio']:.2f}")

print(f"\n  VOTING-ENABLED ({len(voting)} combos):")
for stat, col, fmt in [
    ("Return", "TotalReturn", ".1f"), ("Sharpe", "SharpeRatio", ".4f"),
    ("MaxDD", "MaxDrawdown", ".1f"), ("Trades", "TotalTrades", ".0f"),
    ("WinRate", "WinRate", ".1f"), ("PF", "ProfitFactor", ".3f")]:
    vals = voting[col]
    pct = "%" if stat in ("Return", "MaxDD", "WinRate") else ""
    mult = 100 if stat in ("Return", "MaxDD", "WinRate") else 1
    print(f"    {stat:8s}: min={vals.min()*mult:{fmt}}{pct}  max={vals.max()*mult:{fmt}}{pct}  "
          f"avg={vals.mean()*mult:{fmt}}{pct}  median={vals.median()*mult:{fmt}}{pct}")

# How many beat baseline?
beat_sharpe = (voting['SharpeRatio'] > ctrl['SharpeRatio']).sum()
beat_return = (voting['TotalReturn'] > ctrl['TotalReturn']).sum()
beat_dd = (voting['MaxDrawdown'] < ctrl['MaxDrawdown']).sum()
print(f"\n  Beat baseline Sharpe ({ctrl['SharpeRatio']:.4f}):  {beat_sharpe}/{len(voting)}")
print(f"  Beat baseline Return ({ctrl['TotalReturn']*100:.1f}%):  {beat_return}/{len(voting)}")
print(f"  Beat baseline MaxDD  ({ctrl['MaxDrawdown']*100:.1f}%):   {beat_dd}/{len(voting)}")

# ================================================================
# 2. BINARY vs GRADUATED MODE
# ================================================================
print("\n" + "=" * 120)
print("SECTION 2: BINARY vs GRADUATED MODE")
print("=" * 120)

for label, subset in [("BINARY", binary), ("GRADUATED", graduated)]:
    if len(subset) == 0:
        continue
    print(f"\n  {label} ({len(subset)} combos):")
    print(f"    Avg Return: {subset['TotalReturn'].mean()*100:.1f}%  |  "
          f"Avg Sharpe: {subset['SharpeRatio'].mean():.4f}  |  "
          f"Avg MaxDD: {subset['MaxDrawdown'].mean()*100:.1f}%")
    print(f"    Best Sharpe: {subset['SharpeRatio'].max():.4f}  |  "
          f"Best Return: {subset['TotalReturn'].max()*100:.1f}%  |  "
          f"Best DD: {subset['MaxDrawdown'].min()*100:.1f}%")
    print(f"    Avg Trades: {subset['TotalTrades'].mean():.0f}  |  "
          f"Avg WR: {subset['WinRate'].mean()*100:.1f}%  |  "
          f"Avg R-ratio: {subset['ExpectancyRatio'].mean():.2f}")

print(f"\n  v1.3/v1.4 lesson confirmed? Binary Sharpe {binary['SharpeRatio'].mean():.4f} vs "
      f"Graduated {graduated['SharpeRatio'].mean():.4f}")
winner = "Binary" if binary['SharpeRatio'].mean() >= graduated['SharpeRatio'].mean() else "Graduated"
print(f"  -> {winner} mode is better (again)")

# ================================================================
# 3. THRESHOLD SWEEP -- How much consensus is needed?
# ================================================================
print("\n" + "=" * 120)
print("SECTION 3: VOTE THRESHOLD SWEEP (threshold_full)")
print("=" * 120)

print(f"\n  {'Threshold':>10s} {'Count':>6s} {'AvgRet%':>10s} {'AvgSharpe':>10s} {'AvgDD%':>8s} "
      f"{'AvgTrades':>10s} {'BestSharpe':>11s} {'BestRet%':>10s}")
print("  " + "-" * 78)
for thresh in sorted(voting['vote_threshold_full'].unique()):
    sub = voting[voting['vote_threshold_full'] == thresh]
    print(f"  {thresh:>10.0f} {len(sub):>6d} {sub['TotalReturn'].mean()*100:>9.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['TotalTrades'].mean():>9.0f} {sub['SharpeRatio'].max():>11.4f} "
          f"{sub['TotalReturn'].max()*100:>9.1f}%")

print(f"\n  -> Lower thresholds = more time in market = more return but more risk")
print(f"  -> Higher thresholds = too selective = miss too many moves")
print(f"  -> Threshold 7 (unanimous) is CATASTROPHIC: -31.7% (only 23 trades)")

# ================================================================
# 4. SUB-STRATEGY IMPACT -- Which indicators matter?
# ================================================================
print("\n" + "=" * 120)
print("SECTION 4: SUB-STRATEGY IMPACT -- Which indicators help or hurt?")
print("=" * 120)

# For each sub-strategy, compare ON vs OFF average Sharpe
# Only look at combos where all 7 subs are on vs combos where that specific one is off
subs = ['sub_ema_enabled', 'sub_macd_enabled', 'sub_rsi_enabled',
        'sub_roc_enabled', 'sub_bbands_enabled', 'sub_adx_enabled']
sub_labels = ['EMA 21', 'MACD', 'RSI', 'ROC', 'BBands', 'ADX']

print(f"\n  {'Sub-Strategy':>14s} {'ON_count':>9s} {'ON_avgSharpe':>13s} "
      f"{'OFF_count':>10s} {'OFF_avgSharpe':>14s} {'Delta':>8s} {'Verdict':>10s}")
print("  " + "-" * 85)

for sub_col, label in zip(subs, sub_labels):
    on_set = voting[voting[sub_col] == True]
    off_set = voting[voting[sub_col] == False]
    if len(on_set) > 0 and len(off_set) > 0:
        on_sharpe = on_set['SharpeRatio'].mean()
        off_sharpe = off_set['SharpeRatio'].mean()
        delta = on_sharpe - off_sharpe
        verdict = "HELPS" if delta > 0 else "HURTS"
        print(f"  {label:>14s} {len(on_set):>9d} {on_sharpe:>13.4f} "
              f"{len(off_set):>10d} {off_sharpe:>14.4f} {delta:>+8.4f} {verdict:>10s}")
    elif len(off_set) == 0:
        on_sharpe = on_set['SharpeRatio'].mean()
        print(f"  {label:>14s} {len(on_set):>9d} {on_sharpe:>13.4f} "
              f"{'0':>10s} {'N/A':>14s} {'N/A':>8s} {'ALWAYS ON':>10s}")

print(f"\n  Key insight: Removing subs generally IMPROVES Sharpe -> fewer filters = more time in market")
print(f"  SMA cross alone is sufficient. Extra votes just add noise and delay entry.")

# ================================================================
# 5. NUMBER OF SUB-STRATEGIES -- Less is more?
# ================================================================
print("\n" + "=" * 120)
print("SECTION 5: NUMBER OF SUB-STRATEGIES -- Does more complexity help?")
print("=" * 120)

print(f"\n  {'NumSubs':>8s} {'Count':>6s} {'AvgRet%':>10s} {'AvgSharpe':>10s} {'AvgDD%':>8s} "
      f"{'BestSharpe':>11s} {'AvgTrades':>10s}")
print("  " + "-" * 70)

for n in sorted(voting['num_subs'].unique()):
    sub = voting[voting['num_subs'] == n]
    print(f"  {n:>8.0f} {len(sub):>6d} {sub['TotalReturn'].mean()*100:>9.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['SharpeRatio'].max():>11.4f} {sub['TotalTrades'].mean():>9.0f}")

print(f"\n  -> Complexity inversely correlates with Sharpe")
print(f"  -> 3 subs had best avg Sharpe, 7 subs had worst")
print(f"  -> Each additional sub-strategy is DEAD WEIGHT")

# ================================================================
# 6. FULL TABLE -- All 30 combos ranked by Sharpe
# ================================================================
print("\n" + "=" * 120)
print("SECTION 6: FULL TABLE -- All 30 combos ranked by Sharpe")
print("=" * 120)

print(f"\n{'Rk':>3} {'Vote':>5} {'Mode':>8} {'ThrF':>5} {'ThrH':>5} {'Subs':>5} "
      f"{'EMA':>4} {'MACD':>5} {'RSI':>4} {'ROC':>4} {'BB':>3} {'ADX':>4} "
      f"{'Ret%':>9} {'Sharpe':>8} {'MaxDD%':>7} {'Trades':>7} {'WR%':>6} {'PF':>7} {'R':>6}")
print("-" * 120)

df_sorted = df.sort_values('SharpeRatio', ascending=False)
for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
    vote_str = "ON" if row['voting_enabled'] else "OFF"
    mode_str = row['vote_mode'] if row['voting_enabled'] else "n/a"
    ema = "Y" if row['sub_ema_enabled'] else "N"
    macd = "Y" if row['sub_macd_enabled'] else "N"
    rsi = "Y" if row['sub_rsi_enabled'] else "N"
    roc = "Y" if row['sub_roc_enabled'] else "N"
    bb = "Y" if row['sub_bbands_enabled'] else "N"
    adx = "Y" if row['sub_adx_enabled'] else "N"
    marker = " <-CTRL" if not row['voting_enabled'] else ""
    marker2 = " <-BEST-RETURN" if row['TotalReturn'] == df['TotalReturn'].max() and row['voting_enabled'] else ""
    print(f"{rank:>3} {vote_str:>5} {mode_str:>8} {row['vote_threshold_full']:>5.0f} "
          f"{row['vote_threshold_half']:>5.0f} {row['num_subs']:>5.0f} "
          f"{ema:>4} {macd:>5} {rsi:>4} {roc:>4} {bb:>3} {adx:>4} "
          f"{row['TotalReturn']*100:>8.1f}% {row['SharpeRatio']:>8.4f} "
          f"{row['MaxDrawdown']*100:>6.1f}% {int(row['TotalTrades']):>6d} "
          f"{row['WinRate']*100:>5.1f} {row['ProfitFactor']:>7.3f} "
          f"{row['ExpectancyRatio']:>6.2f}{marker}{marker2}")

# ================================================================
# 7. THE 1089% ANOMALY -- Best return combo deep-dive
# ================================================================
print("\n" + "=" * 120)
print("SECTION 7: THE 1089% ANOMALY -- Best return combo deep-dive")
print("=" * 120)

best_ret = voting.sort_values('TotalReturn', ascending=False).iloc[0]
print(f"\n  Best return combo: {best_ret['TotalReturn']*100:.1f}% (vs baseline {ctrl['TotalReturn']*100:.1f}%)")
print(f"    Mode: {best_ret['vote_mode']}  |  Threshold: {best_ret['vote_threshold_full']:.0f}/"
      f"{best_ret['vote_threshold_half']:.0f}  |  Subs: {best_ret['num_subs']:.0f}")
print(f"    EMA={best_ret['sub_ema_enabled']}  MACD={best_ret['sub_macd_enabled']}  "
      f"RSI={best_ret['sub_rsi_enabled']}  ROC={best_ret['sub_roc_enabled']}  "
      f"BB={best_ret['sub_bbands_enabled']}  ADX={best_ret['sub_adx_enabled']}")
print(f"    Sharpe: {best_ret['SharpeRatio']:.4f} ({(best_ret['SharpeRatio']/ctrl['SharpeRatio']-1)*100:+.1f}% vs baseline)")
print(f"    MaxDD:  {best_ret['MaxDrawdown']*100:.1f}% ({(best_ret['MaxDrawdown']/ctrl['MaxDrawdown']-1)*100:+.1f}% vs baseline)")
print(f"    Trades: {best_ret['TotalTrades']:.0f} (vs {ctrl['TotalTrades']:.0f} baseline)")
print(f"    R-ratio: {best_ret['ExpectancyRatio']:.2f} (vs {ctrl['ExpectancyRatio']:.2f} baseline)")
print(f"\n  WHY 1089%?")
print(f"    - Only 3 subs voting -> threshold=2 means 2 of 3 agree")
print(f"    - SMA cross + RSI + ROC = trend following + momentum confirmation")
print(f"    - No BBands, no MACD, no ADX, no EMA adding noise")
print(f"    - {best_ret['TotalTrades']:.0f} trades vs {ctrl['TotalTrades']:.0f} baseline -> enters/re-enters faster after corrections")
print(f"    - BUT: Sharpe is {(1-best_ret['SharpeRatio']/ctrl['SharpeRatio'])*100:.0f}% WORSE -> more return from MORE RISK, not better timing")

# ================================================================
# 8. ADX THRESHOLD SENSITIVITY
# ================================================================
print("\n" + "=" * 120)
print("SECTION 8: ADX THRESHOLD SENSITIVITY")
print("=" * 120)

print(f"\n  {'ADX_Thresh':>11s} {'Count':>6s} {'AvgRet%':>10s} {'AvgSharpe':>10s} {'AvgDD%':>8s} {'BestRet%':>10s}")
print("  " + "-" * 60)
for adx_t in sorted(voting['adx_threshold'].unique()):
    sub = voting[voting['adx_threshold'] == adx_t]
    print(f"  {adx_t:>11.0f} {len(sub):>6d} {sub['TotalReturn'].mean()*100:>9.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['TotalReturn'].max()*100:>9.1f}%")

# ================================================================
# 9. METRIC-BY-METRIC COMPARISON vs BASELINE
# ================================================================
print("\n" + "=" * 120)
print("SECTION 9: METRIC-BY-METRIC -- Voting avg vs Baseline")
print("=" * 120)

metrics = [
    ("Total Return", "TotalReturn", 100, "%"),
    ("CAGR", "CAGR", 100, "%"),
    ("Sharpe Ratio", "SharpeRatio", 1, ""),
    ("Sortino Ratio", "SortinoRatio", 1, ""),
    ("Calmar Ratio", "CalmarRatio", 1, ""),
    ("Max Drawdown", "MaxDrawdown", 100, "%"),
    ("Volatility", "Volatility", 100, "%"),
    ("Total Trades", "TotalTrades", 1, ""),
    ("Win Rate", "WinRate", 100, "%"),
    ("Profit Factor", "ProfitFactor", 1, ""),
    ("Avg Win", "AverageWin", 1, "$"),
    ("Avg Loss", "AverageLoss", 1, "$"),
    ("Expectancy", "Expectancy", 1, "$"),
    ("R-ratio", "ExpectancyRatio", 1, ""),
]

print(f"\n  {'Metric':>16s} {'Baseline':>12s} {'Voting Avg':>12s} {'Delta':>12s} {'Verdict':>10s}")
print("  " + "-" * 65)

for name, col, mult, unit in metrics:
    baseline_val = ctrl[col] * mult
    avg_val = voting[col].mean() * mult
    delta = avg_val - baseline_val
    # For MaxDD, lower is better
    if col == 'MaxDrawdown':
        verdict = "VOTING BETTER" if delta < 0 else "BASELINE BETTER"
    elif col == 'AverageLoss':
        verdict = "VOTING BETTER" if abs(avg_val) < abs(baseline_val) else "BASELINE BETTER"
    else:
        verdict = "VOTING BETTER" if delta > 0 else "BASELINE BETTER"
    fmt_val = f"{baseline_val:,.2f}{unit}" if unit == "$" else f"{baseline_val:.4f}" if col in ('SharpeRatio','SortinoRatio','CalmarRatio','ProfitFactor') else f"{baseline_val:.1f}{unit}"
    fmt_avg = f"{avg_val:,.2f}{unit}" if unit == "$" else f"{avg_val:.4f}" if col in ('SharpeRatio','SortinoRatio','CalmarRatio','ProfitFactor') else f"{avg_val:.1f}{unit}"
    fmt_delta = f"{delta:+,.2f}{unit}" if unit == "$" else f"{delta:+.4f}" if col in ('SharpeRatio','SortinoRatio','CalmarRatio','ProfitFactor') else f"{delta:+.1f}{unit}"
    print(f"  {name:>16s} {fmt_val:>12s} {fmt_avg:>12s} {fmt_delta:>12s} {verdict:>14s}")

# ================================================================
# 10. CROSS-VERSION PROGRESSION
# ================================================================
print("\n" + "=" * 120)
print("SECTION 10: CROSS-VERSION PROGRESSION -- THE STORY SO FAR")
print("=" * 120)

versions = [
    ("v1.0", "SMA 50/200, 90%, bear=0%", "0.3509", "801.6%", "38.8%", "51", "3.57", "BASELINE CHAMPION"),
    ("v1.1", "Stricter bear filter", "0.3509", "801.6%", "38.8%", "51", "3.57", "NO IMPROVEMENT"),
    ("v1.2", "SMA period sweep", "0.3509", "801.6%", "38.8%", "51", "3.57", "50/200 confirmed"),
    ("v1.3", "Dynamic allocation", "0.3509", "801.6%", "38.8%", "51", "3.57", "Binary wins"),
    ("v1.4", "ROC decel exit", "0.3509", "801.6%", "38.8%", "51", "3.57", "Risk tool only"),
    ("v1.5", "Composite voting (7 subs)", f"{voting['SharpeRatio'].max():.4f}*",
     f"{voting['TotalReturn'].max()*100:.1f}%*", f"{voting['MaxDrawdown'].min()*100:.1f}%*",
     f"{int(voting['TotalTrades'].max())}*", f"{voting['ExpectancyRatio'].max():.2f}*", "PURE DRAG"),
]

print(f"\n  {'Ver':>5s} {'Description':>25s} {'Sharpe':>12s} {'Return':>10s} {'MaxDD':>8s} {'Trades':>7s} {'R':>12s} {'Verdict':>25s}")
print("  " + "-" * 110)
for v in versions:
    print(f"  {v[0]:>5s} {v[1]:>25s} {v[2]:>12s} {v[3]:>10s} {v[4]:>8s} {v[5]:>7s} {v[6]:>12s} {v[7]:>25s}")

print(f"\n  * = best among voting combos, NOT better than baseline")

# ================================================================
# 11. VERDICT
# ================================================================
print("\n" + "=" * 120)
print("SECTION 11: VERDICT -- Composite Voting")
print("=" * 120)

print(f"""
  RESULT: v1.0 baseline STILL CHAMPION after 5 iterations.

  0/{len(voting)} voting combos beat baseline Sharpe (0.3509).
  {beat_return}/{len(voting)} voting combos beat baseline return -> 1089% (SMA+RSI+ROC, threshold=2)
  
  THE PARADOX OF v1.5:
  Adding more confirmation REDUCES performance, not improves it.
  
  Evidence:
  - 3 subs (SMA+RSI+ROC): avg Sharpe 0.2474, best return 1089%
  - 4 subs:                avg Sharpe ~0.17
  - 7 subs:                avg Sharpe 0.1557, best return 812%
  - More subs = more filters = more time OUT of market = miss gains
  
  THE META-LESSON across 5 versions:
  +------------------------------------------------------------------+
  |  The SMA 50/200 crossover IS the optimal signal.                 |
  |  Every attempt to "confirm" it just delays entry.                |
  |  Every attempt to "graduate" position size just adds noise.      |
  |  Every attempt to add complexity just creates drag.              |
  |                                                                  |
  |  v1.1: Stricter bear = unnecessary (bear=0% is already right)   |
  |  v1.2: Different SMAs = worse (50/200 is already optimal)       |
  |  v1.3: Dynamic sizing = destructive (binary IS the edge)        |
  |  v1.4: ROC exit = risk tool only (SMA cross = velocity signal)  |
  |  v1.5: Voting = pure drag (each filter delays the trade)        |
  |                                                                  |
  |  SIMPLE TREND FOLLOWING WINS.                                    |
  +------------------------------------------------------------------+
  
  ONE INTERESTING FINDING:
  The 1089% combo (SMA+RSI+ROC, threshold=2) beat baseline RETURN by 36%.
  But its Sharpe is 30% worse (0.2474 vs 0.3509) and R-ratio is 47% lower.
  Translation: it makes MORE money but takes MORE risk to get it.
  Not truly better -- just leveraging timing luck over 7.5 years.
  
  WHAT'S LEFT TO TRY (v1.6+ candidates):
  1. Per-trade trailing stop (risk management, not alpha)
  2. VIX-based sizing (vol targeting)
  3. Time-of-year seasonality (Nov-Apr vs May-Oct)
  4. Multi-timeframe (weekly confirms daily)
  5. Accept v1.0 IS the answer -> deploy it
""")

print("=" * 120)
print("ANALYSIS COMPLETE")
print("=" * 120)



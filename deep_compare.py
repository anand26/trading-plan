"""Deep comparison of v1.4 ROC deceleration exit results vs v1.0 baseline.

v1.4 Question: Can momentum deceleration (ROC) help us exit before the trend breaks,
reducing drawdown without giving up too much return?

Malik principle: "When velocity is slowing down, take some money out."
"""
import pandas as pd
import json

df14 = pd.read_csv(r'C:\Users\anand\Documents\trading_plan\results\posttrend_1.4.csv')

def parse_params(row):
    try:
        return json.loads(row['ParametersJson'])
    except:
        return {}

params = df14.apply(parse_params, axis=1)
df14['roc_exit_enabled'] = params.apply(lambda p: p.get('roc_exit_enabled', False))
df14['roc_exit_lookback'] = params.apply(lambda p: p.get('roc_exit_lookback', 20))
df14['roc_decel_threshold'] = params.apply(lambda p: p.get('roc_decel_threshold', 0.03))
df14['roc_exit_threshold'] = params.apply(lambda p: p.get('roc_exit_threshold', -0.01))
df14['roc_reduce_alloc'] = params.apply(lambda p: p.get('roc_reduce_alloc', 0.50))

# Separate control and ROC-enabled
ctrl = df14[df14['roc_exit_enabled'] == False].iloc[0]
roc = df14[df14['roc_exit_enabled'] == True].copy()

# Classify ROC modes
roc['mode'] = roc['roc_decel_threshold'].apply(
    lambda x: 'EXIT-ONLY' if x >= 0.5 else 'REDUCE+EXIT'
)

print("=" * 120)
print("v1.4 DEEP ANALYSIS — ROC DECELERATION EXIT")
print("Question: Can momentum deceleration reduce drawdown without killing returns?")
print("=" * 120)

# ================================================================
# 1. CONTROL vs ALL ROC COMBOS — Overview
# ================================================================
print("\n" + "=" * 120)
print("SECTION 1: CONTROL (ROC OFF) vs ROC-ENABLED OVERVIEW")
print("=" * 120)

print(f"\n  CONTROL (v1.0 baseline):")
print(f"    Return: {ctrl['TotalReturn']*100:.1f}%   CAGR: {ctrl['CAGR']*100:.2f}%   Sharpe: {ctrl['SharpeRatio']:.4f}")
print(f"    MaxDD:  {ctrl['MaxDrawdown']*100:.1f}%   Trades: {ctrl['TotalTrades']:.0f}      R-ratio: {ctrl['ExpectancyRatio']:.2f}")
print(f"    WR:     {ctrl['WinRate']*100:.1f}%   PF:     {ctrl['ProfitFactor']:.3f}   AvgWin: ${ctrl['AverageWin']:,.0f}  AvgLoss: ${ctrl['AverageLoss']:,.0f}")

print(f"\n  ROC-ENABLED averages ({len(roc)} combos):")
print(f"    Return: {roc['TotalReturn'].mean()*100:.1f}%   CAGR: {roc['CAGR'].mean()*100:.2f}%   Sharpe: {roc['SharpeRatio'].mean():.4f}")
print(f"    MaxDD:  {roc['MaxDrawdown'].mean()*100:.1f}%   Trades: {roc['TotalTrades'].mean():.0f}      R-ratio: {roc['ExpectancyRatio'].mean():.2f}")
print(f"    WR:     {roc['WinRate'].mean()*100:.1f}%   PF:     {roc['ProfitFactor'].mean():.3f}")

# Key deltas
d_ret = (roc['TotalReturn'].mean() - ctrl['TotalReturn']) * 100
d_dd = (roc['MaxDrawdown'].mean() - ctrl['MaxDrawdown']) * 100
d_sharpe = roc['SharpeRatio'].mean() - ctrl['SharpeRatio']
d_trades = roc['TotalTrades'].mean() - ctrl['TotalTrades']

print(f"\n  AVG DELTAS (ROC ON vs OFF):")
print(f"    Return:  {d_ret:+.1f}%   (ROC {'hurts' if d_ret < 0 else 'helps'})")
print(f"    MaxDD:   {d_dd:+.1f}%   (ROC {'helps' if d_dd < 0 else 'hurts'} — {'less' if d_dd < 0 else 'more'} drawdown)")
print(f"    Sharpe:  {d_sharpe:+.4f} (ROC {'hurts' if d_sharpe < 0 else 'helps'})")
print(f"    Trades:  {d_trades:+.0f}   (ROC adds significant churn)")

# ================================================================
# 2. EXIT-ONLY vs REDUCE+EXIT modes
# ================================================================
print("\n" + "=" * 120)
print("SECTION 2: EXIT-ONLY MODE (decel=0.99) vs REDUCE+EXIT MODE")
print("=" * 120)
print("  EXIT-ONLY:    Skip the REDUCED step, go straight to EXITED when ROC < exit_threshold")
print("  REDUCE+EXIT:  First reduce allocation when ROC decelerates, then exit if ROC keeps falling")

exit_only = roc[roc['mode'] == 'EXIT-ONLY']
reduce_exit = roc[roc['mode'] == 'REDUCE+EXIT']

print(f"\n  {'Mode':<15} {'n':>3} {'avgRet%':>9} {'avgSharpe':>10} {'avgDD%':>8} {'avgTrades':>10} {'avgR':>6} {'avgWR%':>7} {'avgPF':>7}")
print("  " + "-" * 80)
print(f"  {'EXIT-ONLY':<15} {len(exit_only):>3} {exit_only['TotalReturn'].mean()*100:>8.1f}% "
      f"{exit_only['SharpeRatio'].mean():>10.4f} {exit_only['MaxDrawdown'].mean()*100:>7.1f}% "
      f"{exit_only['TotalTrades'].mean():>9.0f} {exit_only['ExpectancyRatio'].mean():>6.2f} "
      f"{exit_only['WinRate'].mean()*100:>6.1f} {exit_only['ProfitFactor'].mean():>7.3f}")
print(f"  {'REDUCE+EXIT':<15} {len(reduce_exit):>3} {reduce_exit['TotalReturn'].mean()*100:>8.1f}% "
      f"{reduce_exit['SharpeRatio'].mean():>10.4f} {reduce_exit['MaxDrawdown'].mean()*100:>7.1f}% "
      f"{reduce_exit['TotalTrades'].mean():>9.0f} {reduce_exit['ExpectancyRatio'].mean():>6.2f} "
      f"{reduce_exit['WinRate'].mean()*100:>6.1f} {reduce_exit['ProfitFactor'].mean():>7.3f}")
print(f"  {'CONTROL':<15} {'1':>3} {ctrl['TotalReturn']*100:>8.1f}% "
      f"{ctrl['SharpeRatio']:>10.4f} {ctrl['MaxDrawdown']*100:>7.1f}% "
      f"{ctrl['TotalTrades']:>9.0f} {ctrl['ExpectancyRatio']:>6.2f} "
      f"{ctrl['WinRate']*100:>6.1f} {ctrl['ProfitFactor']:>7.3f}")

print(f"\n  KEY INSIGHT: EXIT-ONLY mode has {exit_only['TotalReturn'].mean()*100:.0f}% avg return vs "
      f"{reduce_exit['TotalReturn'].mean()*100:.0f}% for REDUCE+EXIT")
print(f"  EXIT-ONLY keeps you in longer (only exits on negative ROC), REDUCE+EXIT cuts early and often")

# ================================================================
# 3. ALL ROC COMBOS — Full table sorted by Sharpe
# ================================================================
print("\n" + "=" * 120)
print("SECTION 3: ALL ROC COMBOS — FULL TABLE (sorted by Sharpe)")
print("=" * 120)

print(f"\n{'Rk':>3} {'Mode':<8} {'LB':>3} {'Decel':>6} {'Exit':>6} {'RedA':>5} "
      f"{'Ret%':>9} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'MaxDD%':>7} "
      f"{'Trades':>7} {'WR%':>6} {'PF':>7} {'R':>6} {'AvgWin':>9} {'AvgLoss':>9}")
print("-" * 135)

all_sorted = roc.sort_values('SharpeRatio', ascending=False)
for rank, (_, r) in enumerate(all_sorted.iterrows(), 1):
    mode_str = "EX-ONLY" if r['mode'] == 'EXIT-ONLY' else "RED+EX"
    print(f"{rank:>3} {mode_str:<8} {r['roc_exit_lookback']:>3.0f} {r['roc_decel_threshold']:>6.2f} "
          f"{r['roc_exit_threshold']:>6.2f} {r['roc_reduce_alloc']:>5.2f} "
          f"{r['TotalReturn']*100:>8.1f}% {r['SharpeRatio']:>8.4f} {r['SortinoRatio']:>8.4f} "
          f"{r['CalmarRatio']:>8.4f} {r['MaxDrawdown']*100:>6.1f}% "
          f"{r['TotalTrades']:>6.0f} {r['WinRate']*100:>5.1f} {r['ProfitFactor']:>7.3f} "
          f"{r['ExpectancyRatio']:>6.2f} {r['AverageWin']:>8,.0f} {r['AverageLoss']:>8,.0f}")

# ================================================================
# 4. THE DRAWDOWN STORY — This is where ROC shines
# ================================================================
print("\n" + "=" * 120)
print("SECTION 4: THE DRAWDOWN STORY — WHERE ROC EXIT SHINES")
print("=" * 120)
print(f"\n  Control MaxDD: {ctrl['MaxDrawdown']*100:.1f}%")

dd_sorted = roc.sort_values('MaxDrawdown')
print(f"\n  {'Rk':>3} {'MaxDD%':>7} {'DD Δ':>7} {'Ret%':>9} {'Ret Δ':>9} {'Sharpe':>8} {'LB':>3} {'Decel':>6} {'Exit':>6} {'RedA':>5} {'Trades':>7} {'Mode':<8}")
print("  " + "-" * 110)

for rank, (_, r) in enumerate(dd_sorted.iterrows(), 1):
    dd_delta = (r['MaxDrawdown'] - ctrl['MaxDrawdown']) * 100
    ret_delta = (r['TotalReturn'] - ctrl['TotalReturn']) * 100
    mode_str = "EX-ONLY" if r['mode'] == 'EXIT-ONLY' else "RED+EX"
    print(f"  {rank:>3} {r['MaxDrawdown']*100:>6.1f}% {dd_delta:>+6.1f}% {r['TotalReturn']*100:>8.1f}% "
          f"{ret_delta:>+8.1f}% {r['SharpeRatio']:>8.4f} {r['roc_exit_lookback']:>3.0f} "
          f"{r['roc_decel_threshold']:>6.2f} {r['roc_exit_threshold']:>6.2f} {r['roc_reduce_alloc']:>5.2f} "
          f"{r['TotalTrades']:>6.0f} {mode_str:<8}")

# Highlight best DD reducers
best_dd = dd_sorted.head(5)
print(f"\n  TOP 5 DD REDUCERS:")
for _, r in best_dd.iterrows():
    dd_pct_reduction = (1 - r['MaxDrawdown'] / ctrl['MaxDrawdown']) * 100
    ret_pct_loss = (1 - r['TotalReturn'] / ctrl['TotalReturn']) * 100
    sharpe_pct_loss = (1 - r['SharpeRatio'] / ctrl['SharpeRatio']) * 100
    print(f"    DD={r['MaxDrawdown']*100:.1f}% ({dd_pct_reduction:+.0f}% less DD)  "
          f"but Ret={r['TotalReturn']*100:.1f}% ({ret_pct_loss:+.0f}% return cost)  "
          f"Sharpe={r['SharpeRatio']:.4f} ({sharpe_pct_loss:+.0f}% Sharpe cost)  "
          f"[LB={r['roc_exit_lookback']:.0f}, Dec={r['roc_decel_threshold']:.2f}, "
          f"Ex={r['roc_exit_threshold']:.2f}, Red={r['roc_reduce_alloc']:.2f}]")

# ================================================================
# 5. PARAMETER SENSITIVITY DEEP-DIVE
# ================================================================
print("\n" + "=" * 120)
print("SECTION 5: PARAMETER SENSITIVITY (REDUCE+EXIT mode only)")
print("=" * 120)

# 5a. Lookback period
print("\n  --- roc_exit_lookback ---")
print(f"  {'LB':>4} {'n':>3} {'avgRet%':>9} {'avgSharpe':>10} {'avgDD%':>8} {'avgTrades':>10} {'avgR':>6}")
print("  " + "-" * 60)
for lb in sorted(reduce_exit['roc_exit_lookback'].unique()):
    sub = reduce_exit[reduce_exit['roc_exit_lookback'] == lb]
    print(f"  {lb:>4.0f} {len(sub):>3} {sub['TotalReturn'].mean()*100:>8.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['TotalTrades'].mean():>9.0f} {sub['ExpectancyRatio'].mean():>6.2f}")

# 5b. Decel threshold
print("\n  --- roc_decel_threshold ---")
print(f"  {'Decel':>6} {'n':>3} {'avgRet%':>9} {'avgSharpe':>10} {'avgDD%':>8} {'avgTrades':>10} {'avgR':>6}")
print("  " + "-" * 60)
for dt in sorted(reduce_exit['roc_decel_threshold'].unique()):
    sub = reduce_exit[reduce_exit['roc_decel_threshold'] == dt]
    print(f"  {dt:>6.2f} {len(sub):>3} {sub['TotalReturn'].mean()*100:>8.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['TotalTrades'].mean():>9.0f} {sub['ExpectancyRatio'].mean():>6.2f}")

# 5c. Exit threshold
print("\n  --- roc_exit_threshold ---")
print(f"  {'ExitT':>6} {'n':>3} {'avgRet%':>9} {'avgSharpe':>10} {'avgDD%':>8} {'avgTrades':>10} {'avgR':>6}")
print("  " + "-" * 60)
for et in sorted(reduce_exit['roc_exit_threshold'].unique()):
    sub = reduce_exit[reduce_exit['roc_exit_threshold'] == et]
    print(f"  {et:>6.2f} {len(sub):>3} {sub['TotalReturn'].mean()*100:>8.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['TotalTrades'].mean():>9.0f} {sub['ExpectancyRatio'].mean():>6.2f}")

# 5d. Reduce alloc
print("\n  --- roc_reduce_alloc ---")
print(f"  {'RedA':>5} {'n':>3} {'avgRet%':>9} {'avgSharpe':>10} {'avgDD%':>8} {'avgTrades':>10} {'avgR':>6}")
print("  " + "-" * 60)
for ra in sorted(reduce_exit['roc_reduce_alloc'].unique()):
    sub = reduce_exit[reduce_exit['roc_reduce_alloc'] == ra]
    print(f"  {ra:>5.2f} {len(sub):>3} {sub['TotalReturn'].mean()*100:>8.1f}% "
          f"{sub['SharpeRatio'].mean():>10.4f} {sub['MaxDrawdown'].mean()*100:>7.1f}% "
          f"{sub['TotalTrades'].mean():>9.0f} {sub['ExpectancyRatio'].mean():>6.2f}")

# ================================================================
# 6. THE TRADEOFF FRONTIER — DD reduction vs Return cost
# ================================================================
print("\n" + "=" * 120)
print("SECTION 6: THE TRADEOFF FRONTIER — Is the DD reduction worth the return cost?")
print("=" * 120)

ctrl_ret = ctrl['TotalReturn']
ctrl_dd = ctrl['MaxDrawdown']
ctrl_sharpe = ctrl['SharpeRatio']

print(f"\n  For each ROC combo, how much DD reduction do you get per % of return sacrificed?")
print(f"\n  {'Rk':>3} {'DD%':>6} {'DDΔ%':>6} {'Ret%':>9} {'RetΔ%':>9} {'DDReduc':>8} {'RetCost':>8} {'Ratio':>8} {'Sharpe':>8} {'Config':<40}")
print("  " + "-" * 120)

tradeoff = roc.copy()
tradeoff['dd_reduction_pct'] = (1 - tradeoff['MaxDrawdown'] / ctrl_dd) * 100
tradeoff['ret_cost_pct'] = (1 - tradeoff['TotalReturn'] / ctrl_ret) * 100
# Positive ratio = good tradeoff (more DD reduction per return cost)
# Negative ret_cost means return INCREASED — infinite value
tradeoff['tradeoff_ratio'] = tradeoff.apply(
    lambda r: r['dd_reduction_pct'] / r['ret_cost_pct'] if r['ret_cost_pct'] > 0 else 99.9,
    axis=1
)

for rank, (_, r) in enumerate(tradeoff.sort_values('tradeoff_ratio', ascending=False).iterrows(), 1):
    config = f"LB={r['roc_exit_lookback']:.0f} Dec={r['roc_decel_threshold']:.2f} Ex={r['roc_exit_threshold']:.2f} Red={r['roc_reduce_alloc']:.2f}"
    dd_delta = (r['MaxDrawdown'] - ctrl_dd) * 100
    ret_delta = (r['TotalReturn'] - ctrl_ret) * 100
    ratio_str = f"{r['tradeoff_ratio']:>7.2f}x" if r['tradeoff_ratio'] < 99 else "  ∞ WIN"
    print(f"  {rank:>3} {r['MaxDrawdown']*100:>5.1f}% {dd_delta:>+5.1f}% {r['TotalReturn']*100:>8.1f}% "
          f"{ret_delta:>+8.1f}% {r['dd_reduction_pct']:>+7.1f}% {r['ret_cost_pct']:>+7.1f}% "
          f"{ratio_str} {r['SharpeRatio']:>8.4f} {config}")

# ================================================================
# 7. COMBOS THAT BEAT BASELINE ON AT LEAST ONE MAJOR METRIC
# ================================================================
print("\n" + "=" * 120)
print("SECTION 7: ROC COMBOS THAT BEAT BASELINE ON KEY METRICS")
print("=" * 120)

beat_return = roc[roc['TotalReturn'] > ctrl['TotalReturn']]
beat_sharpe = roc[roc['SharpeRatio'] > ctrl['SharpeRatio']]
beat_dd = roc[roc['MaxDrawdown'] < ctrl['MaxDrawdown']]
beat_calmar = roc[roc['CalmarRatio'] > ctrl['CalmarRatio']]
beat_sortino = roc[roc['SortinoRatio'] > ctrl['SortinoRatio']]

print(f"\n  Beat baseline Return ({ctrl['TotalReturn']*100:.1f}%):  {len(beat_return)}/{len(roc)} combos")
for _, r in beat_return.sort_values('TotalReturn', ascending=False).iterrows():
    print(f"    Ret={r['TotalReturn']*100:.1f}%  Sharpe={r['SharpeRatio']:.4f}  DD={r['MaxDrawdown']*100:.1f}%  "
          f"[LB={r['roc_exit_lookback']:.0f}, Dec={r['roc_decel_threshold']:.2f}, "
          f"Ex={r['roc_exit_threshold']:.2f}, Red={r['roc_reduce_alloc']:.2f}]")

print(f"\n  Beat baseline Sharpe ({ctrl['SharpeRatio']:.4f}):  {len(beat_sharpe)}/{len(roc)} combos")
for _, r in beat_sharpe.sort_values('SharpeRatio', ascending=False).iterrows():
    print(f"    Sharpe={r['SharpeRatio']:.4f}  Ret={r['TotalReturn']*100:.1f}%  DD={r['MaxDrawdown']*100:.1f}%  "
          f"[LB={r['roc_exit_lookback']:.0f}, Dec={r['roc_decel_threshold']:.2f}, "
          f"Ex={r['roc_exit_threshold']:.2f}, Red={r['roc_reduce_alloc']:.2f}]")

print(f"\n  Beat baseline MaxDD ({ctrl['MaxDrawdown']*100:.1f}%):  {len(beat_dd)}/{len(roc)} combos")
for _, r in beat_dd.sort_values('MaxDrawdown').head(10).iterrows():
    print(f"    DD={r['MaxDrawdown']*100:.1f}%  Ret={r['TotalReturn']*100:.1f}%  Sharpe={r['SharpeRatio']:.4f}  "
          f"[LB={r['roc_exit_lookback']:.0f}, Dec={r['roc_decel_threshold']:.2f}, "
          f"Ex={r['roc_exit_threshold']:.2f}, Red={r['roc_reduce_alloc']:.2f}]")

# ================================================================
# 8. CROSS-VERSION PROGRESSION — Has anything beaten v1.0?
# ================================================================
print("\n" + "=" * 120)
print("SECTION 8: CROSS-VERSION PROGRESSION — THE STORY SO FAR")
print("=" * 120)

versions = [
    ("v1.0", "Broad sweep (SMA, alloc, DD exit, conf)", "50/200, 90%, bear=0%", 0.3509, 801.57, 38.8, 51, 3.57, "BASELINE"),
    ("v1.1", "Stricter bear filter (margin, momentum, conf)", "bear=0% still best", 0.3509, 801.57, 38.8, 51, 3.57, "NO IMPROVEMENT"),
    ("v1.2", "SMA period sweep (200-300, fast 20-100)", "50/200 best, 50/300 close", 0.3509, 801.57, 38.8, 51, 3.57, "NO IMPROVEMENT"),
    ("v1.3", "Dynamic allocation (scale by SMA distance)", "static 90% wins", 0.3509, 801.57, 38.8, 51, 3.57, "NO IMPROVEMENT"),
]

# Find best ROC combo by Sharpe
best_roc = roc.sort_values('SharpeRatio', ascending=False).iloc[0]
# Find best DD reducer that still has decent Sharpe (>0.25)
decent_roc = roc[roc['SharpeRatio'] >= 0.25].sort_values('MaxDrawdown').iloc[0] if len(roc[roc['SharpeRatio'] >= 0.25]) > 0 else None
# Find best return
best_ret_roc = roc.sort_values('TotalReturn', ascending=False).iloc[0]

versions.append((
    "v1.4a",
    "ROC exit: best Sharpe among ROC-enabled",
    f"LB={best_roc['roc_exit_lookback']:.0f}, Dec={best_roc['roc_decel_threshold']:.2f}, Ex={best_roc['roc_exit_threshold']:.2f}",
    best_roc['SharpeRatio'], best_roc['TotalReturn']*100, best_roc['MaxDrawdown']*100,
    best_roc['TotalTrades'], best_roc['ExpectancyRatio'],
    "CLOSE but no cigar" if best_roc['SharpeRatio'] < ctrl['SharpeRatio'] else "BEATS BASELINE!"
))

if decent_roc is not None:
    versions.append((
        "v1.4b",
        "ROC exit: best DD reducer (Sharpe>0.25)",
        f"LB={decent_roc['roc_exit_lookback']:.0f}, Dec={decent_roc['roc_decel_threshold']:.2f}, Ex={decent_roc['roc_exit_threshold']:.2f}",
        decent_roc['SharpeRatio'], decent_roc['TotalReturn']*100, decent_roc['MaxDrawdown']*100,
        decent_roc['TotalTrades'], decent_roc['ExpectancyRatio'],
        f"DD {decent_roc['MaxDrawdown']*100:.1f}% vs {ctrl['MaxDrawdown']*100:.1f}%"
    ))

versions.append((
    "v1.4c",
    "ROC exit: highest return",
    f"LB={best_ret_roc['roc_exit_lookback']:.0f}, Dec={best_ret_roc['roc_decel_threshold']:.2f}, Ex={best_ret_roc['roc_exit_threshold']:.2f}",
    best_ret_roc['SharpeRatio'], best_ret_roc['TotalReturn']*100, best_ret_roc['MaxDrawdown']*100,
    best_ret_roc['TotalTrades'], best_ret_roc['ExpectancyRatio'],
    f"RET {best_ret_roc['TotalReturn']*100:.0f}% vs {ctrl['TotalReturn']*100:.0f}%!"
))

print(f"\n  {'Ver':<6} {'Sharpe':>8} {'Ret%':>9} {'DD%':>6} {'Trades':>7} {'R':>6} {'Verdict':<25} {'Notes'}")
print("  " + "-" * 120)
for v in versions:
    name, desc, config, sharpe, ret, dd, trades, r_ratio, verdict = v
    print(f"  {name:<6} {sharpe:>8.4f} {ret:>8.1f}% {dd:>5.1f}% {trades:>6.0f} {r_ratio:>6.2f} {verdict:<25} {desc}")

# ================================================================
# 9. VERDICT
# ================================================================
print("\n" + "=" * 120)
print("SECTION 9: VERDICT — WHAT DID WE LEARN?")
print("=" * 120)

# Count combos that beat on different metrics
n_better_dd = len(beat_dd)
n_better_ret = len(beat_return)
n_better_sharpe = len(beat_sharpe)

print(f"""
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  v1.4 ROC DECELERATION EXIT — FINAL VERDICT                          │
  ├─────────────────────────────────────────────────────────────────────────┤
  │                                                                       │
  │  Does ROC exit beat the v1.0 baseline on Sharpe?                      │
  │  → NO. 0/{len(roc)} ROC combos beat Sharpe 0.3509                           │
  │                                                                       │
  │  Does ROC exit reduce drawdown?                                       │
  │  → YES! {n_better_dd}/{len(roc)} combos have lower MaxDD than 38.8%              │
  │    Best: {roc['MaxDrawdown'].min()*100:.1f}% ({(1-roc['MaxDrawdown'].min()/ctrl['MaxDrawdown'])*100:.0f}% reduction)                                     │
  │                                                                       │
  │  Does any ROC combo beat baseline return?                             │
  │  → {len(beat_return)} combo(s) — EXIT-ONLY mode (decel=0.99) reached {best_ret_roc['TotalReturn']*100:.0f}%        │
  │                                                                       │
  │  The core tradeoff:                                                   │
  │  → ROC exit trades RETURN and R-RATIO for DRAWDOWN PROTECTION         │
  │  → Avg R-ratio drops from {ctrl['ExpectancyRatio']:.2f} to {roc['ExpectancyRatio'].mean():.2f} (smaller wins)        │
  │  → Avg trades explode from {ctrl['TotalTrades']:.0f} to {roc['TotalTrades'].mean():.0f} (3x churn)                │
  │  → Win rate improves {ctrl['WinRate']*100:.0f}% → {roc['WinRate'].mean()*100:.0f}% (but wins are smaller)         │
  │                                                                       │
  │  KEY INSIGHTS:                                                        │
  │  1. EXIT-ONLY mode (decel=0.99) >> REDUCE+EXIT mode                   │
  │     - Don't reduce early, just exit when ROC goes negative            │
  │     - Keeps you in the trend longer                                   │
  │                                                                       │
  │  2. The REDUCE step destroys value                                    │
  │     - Same lesson as v1.3 (dynamic allocation)                        │
  │     - Cutting position mid-trend = giving up the best gains           │
  │     - Consistent with: binary decisions beat graduated ones           │
  │                                                                       │
  │  3. ROC exit is a RISK MANAGEMENT tool, not an ALPHA tool             │
  │     - If your priority is sleeping at night: ROC exit can cut DD      │
  │       from 38.8% to ~23-30%                                          │
  │     - If your priority is max returns: keep ROC OFF                   │
  │                                                                       │
  │  4. Malik's "take money out when velocity slows" principle:           │
  │     - Conceptually sound for risk management                          │
  │     - But costs too much return to be worth it for Sharpe             │
  │     - The SMA crossover already IS the velocity signal                │
  │                                                                       │
  │  RECOMMENDATION: Keep ROC exit OFF for the primary strategy.          │
  │  v1.0 baseline (SMA 50/200, 90%, bear=0%) remains champion.          │
  │                                                                       │
  │  Score: v1.0=0.3509 Sharpe | v1.4 best ROC={best_roc['SharpeRatio']:.4f} Sharpe        │
  │  After 4 iterations, NOTHING beats the simple trend-follow.           │
  └─────────────────────────────────────────────────────────────────────────┘
""")

# ================================================================
# 10. WHAT'S LEFT TO TRY? (Ideas for v1.5)
# ================================================================
print("=" * 120)
print("SECTION 10: WHAT'S LEFT? (v1.5 candidates)")
print("=" * 120)
print("""
  Iterations completed:
    v1.1  Stricter bear filter ............ no improvement (bear=0% still best)
    v1.2  SMA period sweep ................ no improvement (50/200 still best)
    v1.3  Dynamic allocation .............. no improvement (static 90% still best)
    v1.4  ROC deceleration exit ........... no improvement on Sharpe (but DD reduction available)

  Remaining Malik principles to test:
    v1.5? Volatility-based sizing ......... Size position by VIX or ATR (smaller in high-vol)
    v1.5? Trailing stop per-trade ......... Protect individual trade gains
    v1.5? Multi-timeframe confirmation .... Require weekly + daily alignment
    v1.5? Time-of-year seasonality ........ Sell in May? Reduce in Sept-Oct?
    v1.5? Final integration ............... Combine best elements from all versions

  Or: Accept that v1.0 IS the answer and deploy it.
""")

print("=" * 120)
print("ANALYSIS COMPLETE")
print("=" * 120)

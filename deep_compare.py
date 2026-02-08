"""Deep comparison of v1.2 SMA sweep results vs v1.0/v1.1 baselines."""
import pandas as pd
import json

df12 = pd.read_csv(r'C:\Users\anand\Documents\trading_plan\results\posttrend_1.2.csv')

def parse_params(row):
    try:
        return json.loads(row['ParametersJson'])
    except:
        return {}

params = df12.apply(parse_params, axis=1)
df12['sma_fast'] = params.apply(lambda p: p.get('sma_fast', 50))
df12['sma_slow'] = params.apply(lambda p: p.get('sma_slow', 200))
df12['bear_alloc'] = params.apply(lambda p: p.get('bear_allocation', 0))
df12['bear_confirm'] = params.apply(lambda p: p.get('bear_confirmation_days', 5))

print("=" * 110)
print("v1.2 DEEP ANALYSIS — DOES MALIK'S 250-DAY SMA BEAT OUR 200-DAY?")
print("=" * 110)

# ================================================================
# 1. THE MAIN QUESTION: sma_slow comparison (bear=0% only, clean comparison)
# ================================================================
print("\n" + "=" * 110)
print("SECTION 1: SLOW SMA COMPARISON (bear=0% combos only)")
print("=" * 110)

bear0 = df12[df12['bear_alloc'] == 0.0].copy()

print(f"\n{'SMAf':>5} {'SMAs':>5} {'Ret%':>9} {'CAGR%':>7} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'MaxDD%':>7} {'Trades':>7} {'WR%':>6} {'PF':>7} {'R':>6}")
print("-" * 110)

for _, r in bear0.sort_values(['sma_slow', 'sma_fast']).iterrows():
    marker = " <-- CONTROL" if (r['sma_fast'] == 50 and r['sma_slow'] == 200) else ""
    marker = " <-- MALIK" if (r['sma_fast'] == 50 and r['sma_slow'] == 250) else marker
    print(f"{r['sma_fast']:>5.0f} {r['sma_slow']:>5.0f} {r['TotalReturn']*100:>8.1f}% {r['CAGR']*100:>6.2f}% "
          f"{r['SharpeRatio']:>8.4f} {r['SortinoRatio']:>8.4f} {r['CalmarRatio']:>8.4f} "
          f"{r['MaxDrawdown']*100:>6.1f}% {r['TotalTrades']:>6.0f} {r['WinRate']*100:>5.1f} "
          f"{r['ProfitFactor']:>7.3f} {r['ExpectancyRatio']:>6.4f}{marker}")

# ================================================================
# 2. BEST AT EACH SLOW SMA (bear=0%)
# ================================================================
print("\n" + "=" * 110)
print("SECTION 2: BEST COMBO AT EACH SLOW SMA (bear=0%)")
print("=" * 110)

ctrl = bear0[(bear0['sma_fast'] == 50) & (bear0['sma_slow'] == 200)].iloc[0]
print(f"\nControl: SMA 50/200  Ret={ctrl['TotalReturn']*100:.1f}%  Sharpe={ctrl['SharpeRatio']:.4f}  "
      f"DD={ctrl['MaxDrawdown']*100:.1f}%  Sortino={ctrl['SortinoRatio']:.4f}  Calmar={ctrl['CalmarRatio']:.4f}")
print()

for slow in sorted(bear0['sma_slow'].unique()):
    subset = bear0[bear0['sma_slow'] == slow].sort_values('SharpeRatio', ascending=False)
    best = subset.iloc[0]
    avg_sharpe = subset['SharpeRatio'].mean()
    avg_ret = subset['TotalReturn'].mean()
    
    d_ret = (best['TotalReturn'] - ctrl['TotalReturn']) * 100
    d_sharpe = best['SharpeRatio'] - ctrl['SharpeRatio']
    d_dd = (best['MaxDrawdown'] - ctrl['MaxDrawdown']) * 100
    
    print(f"  SMAs={slow:.0f}  Best: SMAf={best['sma_fast']:.0f}  Ret={best['TotalReturn']*100:.1f}%  "
          f"Sharpe={best['SharpeRatio']:.4f}  DD={best['MaxDrawdown']*100:.1f}%  "
          f"Sortino={best['SortinoRatio']:.4f}  Calmar={best['CalmarRatio']:.4f}  Trades={best['TotalTrades']:.0f}")
    print(f"           Avg: Ret={avg_ret*100:.1f}%  Sharpe={avg_sharpe:.4f}")
    print(f"           vs Control: Ret {d_ret:+.1f}%  Sharpe {d_sharpe:+.4f}  DD {d_dd:+.1f}%")
    print()

# ================================================================
# 3. BEST AT EACH FAST SMA (bear=0%)
# ================================================================
print("=" * 110)
print("SECTION 3: BEST COMBO AT EACH FAST SMA (bear=0%)")
print("=" * 110)

for fast in sorted(bear0['sma_fast'].unique()):
    subset = bear0[bear0['sma_fast'] == fast].sort_values('SharpeRatio', ascending=False)
    best = subset.iloc[0]
    avg_sharpe = subset['SharpeRatio'].mean()
    avg_ret = subset['TotalReturn'].mean()
    
    print(f"  SMAf={fast:.0f}  Best: SMAs={best['sma_slow']:.0f}  Ret={best['TotalReturn']*100:.1f}%  "
          f"Sharpe={best['SharpeRatio']:.4f}  DD={best['MaxDrawdown']*100:.1f}%  "
          f"Sortino={best['SortinoRatio']:.4f}  Trades={best['TotalTrades']:.0f}")
    print(f"          Avg: Ret={avg_ret*100:.1f}%  Sharpe={avg_sharpe:.4f}")

# ================================================================
# 4. SMA 50 FIXED: How does slow SMA affect performance?
# ================================================================
print("\n" + "=" * 110)
print("SECTION 4: SMA_FAST=50 FIXED — SLOW SMA SWEEP (the key question)")
print("=" * 110)

sma50 = bear0[bear0['sma_fast'] == 50].sort_values('sma_slow')
print(f"\n{'SMAs':>5} {'Ret%':>9} {'CAGR%':>7} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'MaxDD%':>7} {'Trades':>7} {'WR%':>6} {'PF':>7} {'AvgWin':>10} {'AvgLoss':>10} {'Net$':>12}")
print("-" * 120)

for _, r in sma50.iterrows():
    net = r['TotalProfit'] - r['TotalLoss']
    marker = " <-- CONTROL" if r['sma_slow'] == 200 else ""
    marker = " <-- MALIK" if r['sma_slow'] == 250 else marker
    print(f"{r['sma_slow']:>5.0f} {r['TotalReturn']*100:>8.1f}% {r['CAGR']*100:>6.2f}% "
          f"{r['SharpeRatio']:>8.4f} {r['SortinoRatio']:>8.4f} {r['CalmarRatio']:>8.4f} "
          f"{r['MaxDrawdown']*100:>6.1f}% {r['TotalTrades']:>6.0f} {r['WinRate']*100:>5.1f} "
          f"{r['ProfitFactor']:>7.3f} {r['AverageWin']:>9,.0f} {r['AverageLoss']:>9,.0f} "
          f"{net:>11,.0f}{marker}")

# ================================================================
# 5. BEAR=30% WITH BEST FILTER: Does slow SMA help there too?
# ================================================================
print("\n" + "=" * 110)
print("SECTION 5: BEAR=30%, CONF=7 — SLOW SMA SWEEP WITH BEAR SIDE ON")
print("=" * 110)

bear30 = df12[df12['bear_alloc'] == 0.3].sort_values('sma_slow')
print(f"\n{'SMAs':>5} {'Ret%':>9} {'CAGR%':>7} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'MaxDD%':>7} {'Trades':>7} {'WR%':>6} {'PF':>7} {'Net$':>12}")
print("-" * 110)

for _, r in bear30.iterrows():
    net = r['TotalProfit'] - r['TotalLoss']
    print(f"{r['sma_slow']:>5.0f} {r['TotalReturn']*100:>8.1f}% {r['CAGR']*100:>6.2f}% "
          f"{r['SharpeRatio']:>8.4f} {r['SortinoRatio']:>8.4f} {r['CalmarRatio']:>8.4f} "
          f"{r['MaxDrawdown']*100:>6.1f}% {r['TotalTrades']:>6.0f} {r['WinRate']*100:>5.1f} "
          f"{r['ProfitFactor']:>7.3f} {net:>11,.0f}")

# ================================================================
# 6. OVERALL TOP 10 (all combos)
# ================================================================
print("\n" + "=" * 110)
print("SECTION 6: OVERALL TOP 10 ACROSS ALL v1.2 COMBOS (by composite)")
print("=" * 110)

# Composite score
for m in ['SharpeRatio', 'CalmarRatio', 'TotalReturn', 'ExpectancyRatio', 'ProfitFactor', 'WinRate']:
    vals = df12[m]
    mn, mx = vals.min(), vals.max()
    rng = mx - mn if mx != mn else 1
    df12[f'_n_{m}'] = (vals - mn) / rng

for m in ['MaxDrawdown']:
    vals = df12[m]
    mn, mx = vals.min(), vals.max()
    rng = mx - mn if mx != mn else 1
    df12[f'_n_{m}'] = 1.0 - (vals - mn) / rng  # lower is better

df12['_score'] = (
    df12['_n_SharpeRatio'] * 0.25 +
    df12['_n_CalmarRatio'] * 0.20 +
    df12['_n_TotalReturn'] * 0.15 +
    df12['_n_ExpectancyRatio'] * 0.10 +
    df12['_n_ProfitFactor'] * 0.10 +
    df12['_n_WinRate'] * 0.10 +
    df12['_n_MaxDrawdown'] * 0.10
)

top10 = df12.sort_values('_score', ascending=False).head(10)
print(f"\n{'Rk':>3} {'Score':>6} {'SMAf':>5} {'SMAs':>5} {'Bear%':>6} {'Ret%':>9} {'Sharpe':>8} {'Sortino':>8} {'Calmar':>8} {'MaxDD%':>7} {'Trades':>7} {'PF':>7}")
print("-" * 100)

for rank, (_, r) in enumerate(top10.iterrows(), 1):
    print(f"{rank:>3} {r['_score']:>6.4f} {r['sma_fast']:>5.0f} {r['sma_slow']:>5.0f} {r['bear_alloc']*100:>5.0f}% "
          f"{r['TotalReturn']*100:>8.1f}% {r['SharpeRatio']:>8.4f} {r['SortinoRatio']:>8.4f} "
          f"{r['CalmarRatio']:>8.4f} {r['MaxDrawdown']*100:>6.1f}% {r['TotalTrades']:>6.0f} "
          f"{r['ProfitFactor']:>7.3f}")

# ================================================================
# 7. VERDICT
# ================================================================
print("\n" + "=" * 110)
print("VERDICT: 200 vs 250 vs 300")
print("=" * 110)

for slow in [200, 250, 300]:
    r = bear0[(bear0['sma_fast'] == 50) & (bear0['sma_slow'] == slow)]
    if len(r) > 0:
        r = r.iloc[0]
        print(f"\n  SMA 50/{slow:.0f}:  Ret={r['TotalReturn']*100:.1f}%  Sharpe={r['SharpeRatio']:.4f}  "
              f"DD={r['MaxDrawdown']*100:.1f}%  Sortino={r['SortinoRatio']:.4f}  Calmar={r['CalmarRatio']:.4f}  "
              f"Trades={r['TotalTrades']:.0f}  PF={r['ProfitFactor']:.3f}")

print("\n" + "=" * 110)
print("ANALYSIS COMPLETE")
print("=" * 110)

"""Deep analysis of 30-combination backtest results."""
import csv, json

rows = []
with open('results/config_b_results.csv') as f:
    reader = csv.DictReader(f)
    for r in reader:
        p = json.loads(r['ParametersJson'])
        rows.append({
            'ret': float(r['TotalReturn'])*100,
            'sharpe': float(r['SharpeRatio']),
            'dd': float(r['MaxDrawdown'])*100,
            'trades': int(r['TotalTrades']),
            'wr': float(r['WinRate'])*100,
            'pf': float(r['ProfitFactor']),
            'cagr': float(r['CAGR'])*100,
            'sortino': float(r['SortinoRatio']),
            'calmar': float(r['CalmarRatio']),
            'avgwin': float(r['AverageWin']),
            'avgloss': float(r['AverageLoss']),
            'sma_f': p['sma_fast'],
            'sma_s': p['sma_slow'],
            'bull': p['bull_allocation'],
            'bear': p['bear_allocation'],
            'cash': p['use_cash_zone'],
            'mixed': p['mixed_allocation'],
            'ddex': p['max_drawdown_exit'],
            'conf': p['confirmation_days'],
        })

# Filter out max_drawdown_exit configs (they killed performance)
good = [r for r in rows if r['ddex'] == 0]

print("=" * 130)
print("DEEP ANALYSIS — 30 PARAMETER COMBINATIONS (excl. DD-exit configs)")
print("=" * 130)
print(f"Total configs without DD exit: {len(good)}")
print()

# Composite score
for r in good:
    r['score'] = (
        r['ret'] / 700 * 0.30 +
        r['sharpe'] / 0.20 * 0.25 +
        r['calmar'] / 5.3 * 0.20 +
        (1 - r['dd'] / 100) * 0.15 +
        r['pf'] / 2.2 * 0.10
    )

good.sort(key=lambda x: x['score'], reverse=True)

hdr = f"{'Rk':>3} {'Ret%':>8} {'CAGR%':>7} {'Sharpe':>7} {'Sortino':>8} {'Calmar':>7} {'DD%':>6} {'Trd':>4} {'WR%':>6} {'PF':>5} {'SMAf':>5} {'SMAs':>5} {'Bull':>5} {'Bear':>5} {'Cash':>5} {'Mix':>5} {'Conf':>5} {'Score':>6}"
print(hdr)
print("-" * len(hdr))
for i, r in enumerate(good):
    cash_str = "ON" if r['cash'] else "OFF"
    print(f"{i+1:>3} {r['ret']:>7.1f}% {r['cagr']:>6.1f}% {r['sharpe']:>7.4f} {r['sortino']:>8.4f} {r['calmar']:>7.4f} {r['dd']:>5.1f}% {r['trades']:>4} {r['wr']:>5.1f}% {r['pf']:>5.2f} {r['sma_f']:>5} {r['sma_s']:>5} {r['bull']:>5.0%} {r['bear']:>5.0%} {cash_str:>5} {r['mixed']:>5.0%} {r['conf']:>5} {r['score']:>6.3f}")

# === KEY INSIGHTS ===
print()
print("=" * 130)
print("KEY INSIGHTS")
print("=" * 130)

# 1. Bear=0 vs Bear>0
bear0 = [r for r in good if r['bear'] == 0]
bearpos = [r for r in good if r['bear'] > 0]
print()
print("1. BEAR ALLOCATION (biggest differentiator)")
print(f"   Bear=0  (cash in bear): avg ret={sum(r['ret'] for r in bear0)/len(bear0):>7.1f}%  avg DD={sum(r['dd'] for r in bear0)/len(bear0):>5.1f}%  avg Sharpe={sum(r['sharpe'] for r in bear0)/len(bear0):>7.4f}  n={len(bear0)}")
print(f"   Bear>0  (SQQQ in bear): avg ret={sum(r['ret'] for r in bearpos)/len(bearpos):>7.1f}%  avg DD={sum(r['dd'] for r in bearpos)/len(bearpos):>5.1f}%  avg Sharpe={sum(r['sharpe'] for r in bearpos)/len(bearpos):>7.4f}  n={len(bearpos)}")

# 2. Cash zone ON vs OFF
cashon = [r for r in good if r['cash']]
cashoff = [r for r in good if not r['cash']]
print()
print("2. CASH ZONE (mixed regime behavior)")
print(f"   Cash=ON  (flat in mixed): avg ret={sum(r['ret'] for r in cashon)/len(cashon):>7.1f}%  avg DD={sum(r['dd'] for r in cashon)/len(cashon):>5.1f}%  avg Sharpe={sum(r['sharpe'] for r in cashon)/len(cashon):>7.4f}  n={len(cashon)}")
print(f"   Cash=OFF (trade mixed):   avg ret={sum(r['ret'] for r in cashoff)/len(cashoff):>7.1f}%  avg DD={sum(r['dd'] for r in cashoff)/len(cashoff):>5.1f}%  avg Sharpe={sum(r['sharpe'] for r in cashoff)/len(cashoff):>7.4f}  n={len(cashoff)}")

# 3. SMA fast
for sf in [20, 50, 100]:
    grp = [r for r in good if r['sma_f'] == sf]
    if grp:
        print(f"   SMAf={sf:>3}: avg ret={sum(r['ret'] for r in grp)/len(grp):>7.1f}%  avg DD={sum(r['dd'] for r in grp)/len(grp):>5.1f}%  avg Sharpe={sum(r['sharpe'] for r in grp)/len(grp):>7.4f}  n={len(grp)}")

# 4. Confirmation days
print()
print("3. CONFIRMATION DAYS")
for cd in [1, 3, 5]:
    grp = [r for r in good if r['conf'] == cd]
    if grp:
        print(f"   Conf={cd}: avg ret={sum(r['ret'] for r in grp)/len(grp):>7.1f}%  avg DD={sum(r['dd'] for r in grp)/len(grp):>5.1f}%  avg Sharpe={sum(r['sharpe'] for r in grp)/len(grp):>7.4f}  avg trades={sum(r['trades'] for r in grp)/len(grp):>5.0f}  n={len(grp)}")

# Top 3 shortlisted
print()
print("=" * 130)
print("TOP 3 CANDIDATES FOR MULTI-TIMEFRAME TESTING")
print("=" * 130)

candidates = [
    ("A", good[0], "HIGHEST RETURN + BEST CALMAR — Pure bull-only, simplest strategy"),
    ("B", good[1], "2ND BEST OVERALL — Same idea, SMA200 instead of 250"),
    ("C", next(r for r in good if r['sma_f'] == 50 and r['sma_s'] == 200 and r['bear'] == 0.5 and not r['cash']), "BEST WITH BEAR HEDGE — Trades all regimes"),
]

for label, r, desc in candidates:
    cash_str = "ON" if r['cash'] else "OFF"
    print(f"""
  Config {label}: {desc}
  ┌───────────────────────────────────────────────────────────────┐
  │ SMA Fast: {r['sma_f']:>3}  │  SMA Slow: {r['sma_s']:>3}  │  Bull: {r['bull']:>4.0%}  │  Bear: {r['bear']:>4.0%}  │
  │ Cash Zone: {cash_str:>3}  │  Mixed: {r['mixed']:>4.0%}   │  Confirm: {r['conf']}     │  DD Exit: {r['ddex']:.0%}  │
  ├───────────────────────────────────────────────────────────────┤
  │ Return: {r['ret']:>7.1f}%  │  CAGR: {r['cagr']:>5.1f}%  │  Sharpe: {r['sharpe']:>6.4f}         │
  │ Sortino: {r['sortino']:>7.4f} │  Calmar: {r['calmar']:>6.4f} │  MaxDD: {r['dd']:>5.1f}%           │
  │ Trades: {r['trades']:>4}     │  WinRate: {r['wr']:>5.1f}% │  PF: {r['pf']:>5.2f}              │
  │ AvgWin: ${r['avgwin']:>10,.0f} │ AvgLoss: ${r['avgloss']:>10,.0f}                   │
  └───────────────────────────────────────────────────────────────┘""")

print()
print("=" * 130)
print("RECOMMENDATION")
print("=" * 130)
print("""
  Config A (SMA50/250, Bull=90%, Bear=0%, Cash=ON) is the CLEAR WINNER:
  
  ✅ Highest return (626.8%) — almost 2x the next best
  ✅ Best risk-adjusted (Sharpe 0.1957, Calmar 4.82)
  ✅ Lowest drawdown among top performers (42.7%)
  ✅ Best R-ratio (3.03 — wins are 3x losses)
  ✅ Simplest — only trades TQQQ in bull, CASH everywhere else
  ✅ Fewest decisions — just 57 trades in 8 years
  
  WHY IT WORKS: The strategy IS regime detection. Going cash in bear
  avoids SQQQ drag. SQQQ is designed to decay, so holding it during
  bear markets HURTS more than it helps (bear>0 underperforms bear=0).
  
  NEXT STEP: Test Config A across different timeframes:
  - 2010-2018 (bull run with corrections)
  - 2018-2020 (volatile with COVID crash)
  - 2020-2026 (current period, strong bull)
  - 2010-2026 (full available history)
""")
input("\n  Press ENTER to close this window...")


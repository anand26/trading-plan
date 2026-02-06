"""Analyze the v4.0 trend filter backtest results."""
import csv
import json

results_file = r"c:\Users\anand\Documents\trading_plan\backtest\trend_filter_results_1.csv"

with open(results_file) as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total backtests: {len(rows)}")
print()

# ========== EXTRACT KEY METRICS ==========
data = []
for r in rows:
    params = json.loads(r['ParametersJson'])
    data.append({
        'hash': params.get('_hash', ''),
        'total_return': float(r['TotalReturn']),
        'cagr': float(r['CAGR']),
        'sharpe': float(r['SharpeRatio']),
        'sortino': float(r['SortinoRatio']),
        'max_dd': float(r['MaxDrawdown']),
        'volatility': float(r['Volatility']),
        'total_trades': int(r['TotalTrades']),
        'win_rate': float(r['WinRate']),
        'profit_factor': float(r['ProfitFactor']),
        'total_profit': float(r['TotalProfit']),
        'total_loss': float(r['TotalLoss']),
        'avg_win': float(r['AverageWin']),
        'avg_loss': float(r['AverageLoss']),
        'largest_win': float(r['LargestWin']),
        'largest_loss': float(r['LargestLoss']),
        # Key params
        'zscore_lookback': params['zscore_lookback'],
        'entry_zscore': params['entry_zscore'],
        'exit_zscore': params['exit_zscore'],
        'stop_zscore': params['stop_zscore'],
        'position_size': params['position_size'],
        'stop_loss_pct': params['stop_loss_pct'],
        'trend_filter': params['trend_filter_enabled'],
        'daily_loss_limit': params['daily_loss_limit_pct'],
        'max_drawdown_pct': params['max_drawdown_pct'],
        'dd_position_scale': params['drawdown_position_scale'],
        'vol_scaling': params['enable_vol_scaling'],
        'warmup_days': params['warmup_days'],
    })

# ========== SORT BY RETURN ==========
data.sort(key=lambda x: x['total_return'], reverse=True)

print("=" * 120)
print("ALL RESULTS (sorted by return)")
print("=" * 120)
print(f"{'#':>2} {'Return':>8} {'Sharpe':>7} {'MaxDD':>7} {'Trades':>6} {'WinR':>6} {'PF':>6} {'AvgW':>7} {'AvgL':>7} {'Key Change'}")
print("-" * 120)

baseline_params = {'zscore_lookback': 46, 'entry_zscore': 1.5, 'exit_zscore': 0.32, 'stop_zscore': 3.0, 'position_size': 0.57, 'stop_loss_pct': 0.02, 'trend_filter': True, 'daily_loss_limit': 0.02, 'max_drawdown_pct': 0.25, 'dd_position_scale': 0.5, 'vol_scaling': False, 'warmup_days': 210}

for i, d in enumerate(data):
    # Find what's different from baseline
    diffs = []
    for k, bv in baseline_params.items():
        if d[k] != bv:
            diffs.append(f"{k}={d[k]}")
    
    key_change = ", ".join(diffs) if diffs else "BASELINE"
    
    print(f"{i+1:>2} {d['total_return']:>7.1%} {d['sharpe']:>7.2f} {d['max_dd']:>7.1%} {d['total_trades']:>6} {d['win_rate']:>5.1%} {d['profit_factor']:>6.3f} ${d['avg_win']:>6.0f} ${d['avg_loss']:>6.0f}  {key_change}")

# ========== KEY ANALYSIS ==========
print("\n" + "=" * 120)
print("KEY OBSERVATIONS")
print("=" * 120)

# 1. Return range
returns = [d['total_return'] for d in data]
print(f"\nReturn range: {min(returns):.1%} to {max(returns):.1%}")
print(f"Median return: {sorted(returns)[len(returns)//2]:.1%}")

# 2. Best performer
best = data[0]
print(f"\nBest: {best['total_return']:.1%} return, {best['sharpe']:.2f} Sharpe, {best['max_dd']:.1%} MaxDD")

# 3. Baseline
baseline = [d for d in data if all(d[k] == v for k, v in baseline_params.items())]
if baseline:
    b = baseline[0]
    print(f"Baseline: {b['total_return']:.1%} return, {b['sharpe']:.2f} Sharpe, {b['max_dd']:.1%} MaxDD, {b['total_trades']} trades")

# 4. No trend filter
no_trend = [d for d in data if not d['trend_filter']]
if no_trend:
    nt = no_trend[0]
    print(f"No trend filter: {nt['total_return']:.1%} return, {nt['sharpe']:.2f} Sharpe, {nt['total_trades']} trades")

# 5. Avg win vs avg loss analysis
print(f"\n--- EDGE QUALITY ---")
for d in data[:5]:
    net_edge_per_trade = d['total_profit'] + d['total_loss']
    avg_pnl = net_edge_per_trade / d['total_trades'] if d['total_trades'] > 0 else 0
    print(f"  Return={d['total_return']:>6.1%}: AvgWin=${d['avg_win']:.0f}, AvgLoss=${d['avg_loss']:.0f}, AvgPnL/trade=${avg_pnl:.0f}, PF={d['profit_factor']:.3f}, NetEdge=${net_edge_per_trade:,.0f} over {d['total_trades']} trades")

# 6. Many parameters have IDENTICAL results
print(f"\n--- DUPLICATE DETECTION ---")
from collections import Counter
return_counts = Counter(d['total_return'] for d in data)
for ret, cnt in return_counts.most_common(5):
    if cnt > 1:
        matching = [d for d in data if d['total_return'] == ret]
        diffs_list = []
        for m in matching:
            diffs = []
            for k, bv in baseline_params.items():
                if m[k] != bv:
                    diffs.append(f"{k}={m[k]}")
            diffs_list.append(", ".join(diffs) if diffs else "BASELINE")
        print(f"  Return {ret:.1%} appears {cnt} times:")
        for dl in diffs_list:
            print(f"    - {dl}")

# 7. What's the actual $ magnitude?
print(f"\n--- TRADE SIZE & P&L MAGNITUDE ---")
b = baseline[0] if baseline else data[0]
print(f"Starting capital: $100,000")
print(f"Position size: {b['position_size']:.0%} = ${100000 * b['position_size']:,.0f} per trade")
print(f"Total trades over period: {b['total_trades']}")
print(f"Total gross profit: ${b['total_profit']:,.0f}")
print(f"Total gross loss: ${b['total_loss']:,.0f}")
print(f"Net P&L: ${b['total_profit'] + b['total_loss']:,.0f}")
print(f"Average win: ${b['avg_win']:.0f} ({b['avg_win']/57000*100:.2f}% of position)")
print(f"Average loss: ${b['avg_loss']:.0f} ({b['avg_loss']/57000*100:.2f}% of position)")
print(f"Largest win: ${b['largest_win']:,.0f} ({b['largest_win']/57000*100:.1f}% of position)")
print(f"Largest loss: ${b['largest_loss']:,.0f} ({b['largest_loss']/57000*100:.1f}% of position)")

print(f"\nNet edge per trade: ${(b['total_profit'] + b['total_loss'])/b['total_trades']:.2f}")
print(f"That's {(b['total_profit'] + b['total_loss'])/b['total_trades']/57000*100:.3f}% per trade on a ${57000:,} position")

# 8. Commissions / cost analysis
daily_trades = b['total_trades'] / 252  # ~252 trading days
print(f"\nAvg trades per day: {daily_trades:.1f}")
print(f"Win rate: {b['win_rate']:.1%}")
print(f"Ratio of avg_win/avg_loss: {b['avg_win']/b['avg_loss']:.2f}")

print(f"\n--- STOP LOSS IMPACT ---")
for d in data:
    if d['stop_loss_pct'] != 0.02 and d.get('trend_filter', True):
        diffs = [k for k, v in baseline_params.items() if d[k] != v]
        print(f"  stop_loss={d['stop_loss_pct']}: Return={d['total_return']:.1%}, Sharpe={d['sharpe']:.2f}, LargestLoss=${d['largest_loss']:,.0f}")

print(f"\n--- POSITION SIZE IMPACT ---")
for d in data:
    if d['position_size'] != 0.57 and d.get('trend_filter', True) and d['stop_loss_pct'] == 0.02:
        print(f"  position_size={d['position_size']}: Return={d['total_return']:.1%}, Sharpe={d['sharpe']:.2f}, MaxDD={d['max_dd']:.1%}")

# 9. Calmar ratios
print(f"\n--- RISK-ADJUSTED RANKINGS (Calmar = CAGR/MaxDD) ---")
for d in data[:10]:
    calmar = d['cagr'] / d['max_dd'] if d['max_dd'] > 0 else 0
    diffs = []
    for k, bv in baseline_params.items():
        if d[k] != bv:
            diffs.append(f"{k}={d[k]}")
    key_change = ", ".join(diffs) if diffs else "BASELINE"
    print(f"  Calmar={calmar:.2f}  Return={d['total_return']:.1%}  MaxDD={d['max_dd']:.1%}  {key_change}")

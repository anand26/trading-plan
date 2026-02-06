"""Analyze v5.0 structural backtest results."""
import csv
import json

rows = []
with open("results/trend_filter_results_2.csv", "r") as f:
    reader = csv.DictReader(f)
    for r in reader:
        params = json.loads(r["ParametersJson"])
        rows.append({
            "row": len(rows) + 1,
            "ret": float(r["TotalReturn"] or 0),
            "sharpe": float(r["SharpeRatio"] or 0),
            "maxdd": float(r["MaxDrawdown"] or 0),
            "trades": int(r["TotalTrades"] or 0),
            "winrate": float(r["WinRate"] or 0),
            "pf": float(r["ProfitFactor"] or 0),
            "avg_win": float(r["AverageWin"] or 0),
            "avg_loss": float(r["AverageLoss"] or 0),
            "vol": float(r["Volatility"] or 0),
            "total_profit": float(r["TotalProfit"] or 0),
            "total_loss": float(r["TotalLoss"] or 0),
            "entry_z": params.get("entry_zscore", 2.0),
            "bars": params.get("min_bars_between", 6),
            "bar_min": params.get("bar_period_minutes", 5),
            "tp": params.get("take_profit_pct", 0),
            "trail_act": params.get("trailing_activation_pct", 0.01),
            "trail": params.get("trailing_stop_pct", 0),
            "vol_scale": params.get("enable_vol_scaling", False),
            "exit_z": params.get("exit_zscore", 0.32),
            "stop": params.get("stop_loss_pct", 0.02),
            "lb": params.get("zscore_lookback", 46),
        })

# Sort by Sharpe
rows.sort(key=lambda x: x["sharpe"], reverse=True)

print("=" * 130)
hdr = f"{'Rk':>2} {'Ret%':>7} {'Sharpe':>7} {'MaxDD%':>7} {'Trades':>6} {'WR%':>6} {'PF':>6} {'AvgW':>7} {'AvgL':>7} {'BarMin':>6} {'EntZ':>5} {'Bars':>4} {'TP%':>5} {'Trail%':>7} {'VS':>3} | Description"
print(hdr)
print("-" * 130)
for rank, r in enumerate(rows, 1):
    tp_str = f"{r['tp']*100:.0f}%" if r["tp"] > 0 else " -"
    trail_str = f"{r['trail_act']*100:.1f}/{r['trail']*100:.1f}" if r["trail"] > 0 else "  -"
    vs_str = "ON" if r["vol_scale"] else " -"
    extra = []
    if r["exit_z"] != 0.32:
        extra.append(f"exZ={r['exit_z']}")
    if r["stop"] != 0.02:
        extra.append(f"stop={r['stop']*100:.1f}%")
    if r["lb"] != 46:
        extra.append(f"LB={r['lb']}")
    desc = ", ".join(extra) if extra else ""
    print(f"{rank:>2} {r['ret']*100:>6.1f}% {r['sharpe']:>7.2f} {r['maxdd']*100:>6.1f}% {r['trades']:>6} {r['winrate']*100:>5.1f} {r['pf']:>6.2f} {r['avg_win']:>7.0f} {r['avg_loss']:>7.0f} {r['bar_min']:>6} {r['entry_z']:>5.1f} {r['bars']:>4} {tp_str:>5} {trail_str:>7} {vs_str:>3} | {desc}")

print()
print("=" * 80)
print("SUMMARY STATS")
print("=" * 80)
rets = [r["ret"] for r in rows]
sharpes = [r["sharpe"] for r in rows]
dds = [r["maxdd"] for r in rows]
profitable = [r for r in rows if r["ret"] > 0]
losing = [r for r in rows if r["ret"] < 0]
sorted_rets = sorted(rets)
sorted_sharpes = sorted(sharpes)
print(f"Profitable: {len(profitable)}/32 ({len(profitable)/32*100:.0f}%)")
print(f"Returns:  min={min(rets)*100:.1f}%  max={max(rets)*100:.1f}%  median={sorted_rets[len(rets)//2]*100:.1f}%")
print(f"Sharpe:   min={min(sharpes):.2f}  max={max(sharpes):.2f}  median={sorted_sharpes[len(sharpes)//2]:.2f}")
print(f"MaxDD:    min={min(dds)*100:.1f}%  max={max(dds)*100:.1f}%")

print()
print("=" * 80)
print("BY BAR PERIOD")
print("=" * 80)
for bp in [5, 15, 30]:
    subset = [r for r in rows if r["bar_min"] == bp]
    if subset:
        avg_ret = sum(r["ret"] for r in subset) / len(subset)
        avg_sharpe = sum(r["sharpe"] for r in subset) / len(subset)
        avg_dd = sum(r["maxdd"] for r in subset) / len(subset)
        avg_trades = sum(r["trades"] for r in subset) / len(subset)
        best = max(subset, key=lambda x: x["sharpe"])
        print(f"{bp:>2}-min: n={len(subset):>2}  avg_ret={avg_ret*100:>6.1f}%  avg_sharpe={avg_sharpe:>6.2f}  avg_dd={avg_dd*100:>5.1f}%  avg_trades={avg_trades:>5.0f}")
        print(f"       best: ret={best['ret']*100:.1f}%  sharpe={best['sharpe']:.2f}  dd={best['maxdd']*100:.1f}%")

print()
print("=" * 80)
print("TRAILING STOP IMPACT (5-min bars, entry=2.0, bars=6, no TP)")
print("=" * 80)
base_filter = lambda r: r["bar_min"] == 5 and r["entry_z"] == 2.0 and r["bars"] == 6 and r["exit_z"] == 0.32 and r["stop"] == 0.02 and not r["vol_scale"] and r["lb"] == 46 and r["tp"] == 0
no_trail = [r for r in rows if base_filter(r) and r["trail"] == 0]
with_trail = [r for r in rows if base_filter(r) and r["trail"] > 0]
if no_trail:
    r = no_trail[0]
    print(f"No trailing:        ret={r['ret']*100:>6.1f}%  sharpe={r['sharpe']:>6.2f}  DD={r['maxdd']*100:.1f}%  trades={r['trades']}")
for t in sorted(with_trail, key=lambda x: x["trail"]):
    print(f"Trail {t['trail_act']*100:.1f}/{t['trail']*100:.1f}%:     ret={t['ret']*100:>6.1f}%  sharpe={t['sharpe']:>6.2f}  DD={t['maxdd']*100:.1f}%  trades={t['trades']}")

print()
print("=" * 80)
print("ENTRY Z-SCORE IMPACT (5-min, trail=0.5%, bars=6)")
print("=" * 80)
for ez in [1.5, 2.0, 2.5]:
    sub = [r for r in rows if r["entry_z"] == ez and r["bar_min"] == 5 and r["trail"] == 0.005 and r["tp"] == 0 and r["exit_z"] == 0.32 and r["stop"] == 0.02 and not r["vol_scale"] and r["lb"] == 46 and r["bars"] == 6]
    for s in sub:
        edge = s["avg_win"] * s["winrate"] - s["avg_loss"] * (1 - s["winrate"])
        print(f"Z={ez:.1f}: ret={s['ret']*100:>6.1f}%  sharpe={s['sharpe']:>6.2f}  DD={s['maxdd']*100:.1f}%  trades={s['trades']:>4}  WR={s['winrate']*100:.1f}%  avgW=${s['avg_win']:.0f}  avgL=${s['avg_loss']:.0f}  edge/trade=${edge:.0f}")

print()
print("=" * 80)
print("TAKE PROFIT IMPACT (5-min, entry=2.0, bars=6, no trail)")
print("=" * 80)
tp_filter = lambda r: r["bar_min"] == 5 and r["entry_z"] == 2.0 and r["bars"] == 6 and r["trail"] == 0 and r["exit_z"] == 0.32 and r["stop"] == 0.02 and not r["vol_scale"] and r["lb"] == 46
for tp_val in [0, 0.02, 0.03, 0.05]:
    sub = [r for r in rows if tp_filter(r) and r["tp"] == tp_val]
    for s in sub:
        tp_label = f"TP={tp_val*100:.0f}%" if tp_val > 0 else "No TP"
        print(f"{tp_label:>7}: ret={s['ret']*100:>6.1f}%  sharpe={s['sharpe']:>6.2f}  DD={s['maxdd']*100:.1f}%  avgW=${s['avg_win']:.0f}  avgL=${s['avg_loss']:.0f}")

print()
print("=" * 80)
print("RE-ENTRY SPACING IMPACT (5-min, entry=2.0, trail=0.5%)")
print("=" * 80)
for bars in [4, 6, 8, 10]:
    sub = [r for r in rows if r["bars"] == bars and r["bar_min"] == 5 and r["entry_z"] == 2.0 and r["trail"] == 0.005 and r["tp"] == 0 and r["exit_z"] == 0.32 and r["stop"] == 0.02 and not r["vol_scale"] and r["lb"] == 46]
    for s in sub:
        print(f"bars={bars:>2}: ret={s['ret']*100:>6.1f}%  sharpe={s['sharpe']:>6.2f}  DD={s['maxdd']*100:.1f}%  trades={s['trades']}")

print()
print("=" * 80)
print("VOL SCALING IMPACT")
print("=" * 80)
vs_off = [r for r in rows if r["bar_min"] == 5 and r["trail"] == 0.005 and r["entry_z"] == 2.0 and r["bars"] == 6 and not r["vol_scale"] and r["exit_z"] == 0.32 and r["stop"] == 0.02 and r["lb"] == 46 and r["tp"] == 0]
vs_on = [r for r in rows if r["bar_min"] == 5 and r["trail"] == 0.005 and r["entry_z"] == 2.0 and r["bars"] == 6 and r["vol_scale"] and r["exit_z"] == 0.32 and r["stop"] == 0.02 and r["lb"] == 46 and r["tp"] == 0]
for s in vs_off:
    print(f"Vol OFF: ret={s['ret']*100:>6.1f}%  sharpe={s['sharpe']:>6.2f}  DD={s['maxdd']*100:.1f}%  vol={s['vol']*100:.1f}%")
for s in vs_on:
    print(f"Vol ON:  ret={s['ret']*100:>6.1f}%  sharpe={s['sharpe']:>6.2f}  DD={s['maxdd']*100:.1f}%  vol={s['vol']*100:.1f}%")

print()
print("=" * 80)
print("STOP LOSS WIDTH (5-min, entry=2.0, trail=0.5%)")
print("=" * 80)
for sl in [0.015, 0.02, 0.025]:
    sub = [r for r in rows if r["stop"] == sl and r["bar_min"] == 5 and r["entry_z"] == 2.0 and r["bars"] == 6 and r["trail"] == 0.005 and r["tp"] == 0 and r["exit_z"] == 0.32 and not r["vol_scale"] and r["lb"] == 46]
    for s in sub:
        print(f"stop={sl*100:.1f}%: ret={s['ret']*100:>6.1f}%  sharpe={s['sharpe']:>6.2f}  DD={s['maxdd']*100:.1f}%  avgW=${s['avg_win']:.0f}  avgL=${s['avg_loss']:.0f}")

print()
print("=" * 80)
print("TOP 5 BY SHARPE")
print("=" * 80)
for i, r in enumerate(rows[:5], 1):
    extras = []
    if r["tp"] > 0: extras.append(f"TP={r['tp']*100:.0f}%")
    if r["trail"] > 0: extras.append(f"trail={r['trail_act']*100:.1f}/{r['trail']*100:.1f}%")
    if r["bar_min"] != 5: extras.append(f"{r['bar_min']}min")
    if r["entry_z"] != 2.0: extras.append(f"entZ={r['entry_z']}")
    if r["vol_scale"]: extras.append("volON")
    if r["exit_z"] != 0.32: extras.append(f"exZ={r['exit_z']}")
    if r["stop"] != 0.02: extras.append(f"stop={r['stop']*100:.1f}%")
    if r["lb"] != 46: extras.append(f"LB={r['lb']}")
    if r["bars"] != 6: extras.append(f"bars={r['bars']}")
    cfg = ", ".join(extras) if extras else "BASELINE"
    print(f"#{i}: Sharpe={r['sharpe']:.2f}  ret={r['ret']*100:.1f}%  DD={r['maxdd']*100:.1f}%  trades={r['trades']}  WR={r['winrate']*100:.1f}%  PF={r['pf']:.2f}  [{cfg}]")

print()
print("=" * 80)
print("TOP 5 BY RETURN")
print("=" * 80)
by_ret = sorted(rows, key=lambda x: x["ret"], reverse=True)
for i, r in enumerate(by_ret[:5], 1):
    extras = []
    if r["tp"] > 0: extras.append(f"TP={r['tp']*100:.0f}%")
    if r["trail"] > 0: extras.append(f"trail={r['trail_act']*100:.1f}/{r['trail']*100:.1f}%")
    if r["bar_min"] != 5: extras.append(f"{r['bar_min']}min")
    if r["entry_z"] != 2.0: extras.append(f"entZ={r['entry_z']}")
    if r["vol_scale"]: extras.append("volON")
    if r["exit_z"] != 0.32: extras.append(f"exZ={r['exit_z']}")
    if r["stop"] != 0.02: extras.append(f"stop={r['stop']*100:.1f}%")
    if r["lb"] != 46: extras.append(f"LB={r['lb']}")
    if r["bars"] != 6: extras.append(f"bars={r['bars']}")
    cfg = ", ".join(extras) if extras else "BASELINE"
    print(f"#{i}: ret={r['ret']*100:.1f}%  Sharpe={r['sharpe']:.2f}  DD={r['maxdd']*100:.1f}%  trades={r['trades']}  [{cfg}]")

print()
print("=" * 80)
print("TOP 5 BY RISK-ADJUSTED (Calmar-like = Return / MaxDD)")
print("=" * 80)
for r in rows:
    r["calmar"] = r["ret"] / r["maxdd"] if r["maxdd"] > 0 else 0
by_calmar = sorted(rows, key=lambda x: x["calmar"], reverse=True)
for i, r in enumerate(by_calmar[:5], 1):
    extras = []
    if r["tp"] > 0: extras.append(f"TP={r['tp']*100:.0f}%")
    if r["trail"] > 0: extras.append(f"trail={r['trail_act']*100:.1f}/{r['trail']*100:.1f}%")
    if r["bar_min"] != 5: extras.append(f"{r['bar_min']}min")
    if r["entry_z"] != 2.0: extras.append(f"entZ={r['entry_z']}")
    if r["vol_scale"]: extras.append("volON")
    if r["exit_z"] != 0.32: extras.append(f"exZ={r['exit_z']}")
    if r["stop"] != 0.02: extras.append(f"stop={r['stop']*100:.1f}%")
    if r["lb"] != 46: extras.append(f"LB={r['lb']}")
    if r["bars"] != 6: extras.append(f"bars={r['bars']}")
    cfg = ", ".join(extras) if extras else "BASELINE"
    print(f"#{i}: Calmar={r['calmar']:.2f}  ret={r['ret']*100:.1f}%  DD={r['maxdd']*100:.1f}%  Sharpe={r['sharpe']:.2f}  [{cfg}]")

# v4.0 old baseline comparison
print()
print("=" * 80)
print("v4.0 OLD BASELINE vs v5.0 NEW BASELINE")
print("=" * 80)
old = [r for r in rows if r["entry_z"] == 1.5 and r["bars"] == 3 and r["bar_min"] == 5 and r["trail"] == 0 and r["tp"] == 0]
new = [r for r in rows if r["entry_z"] == 2.0 and r["bars"] == 6 and r["bar_min"] == 5 and r["trail"] == 0 and r["tp"] == 0 and r["exit_z"] == 0.32 and r["stop"] == 0.02 and not r["vol_scale"] and r["lb"] == 46]
if old:
    r = old[0]
    print(f"OLD (Z=1.5, bars=3): ret={r['ret']*100:.1f}%  sharpe={r['sharpe']:.2f}  DD={r['maxdd']*100:.1f}%  trades={r['trades']}  WR={r['winrate']*100:.1f}%  PF={r['pf']:.2f}")
if new:
    r = new[0]
    print(f"NEW (Z=2.0, bars=6): ret={r['ret']*100:.1f}%  sharpe={r['sharpe']:.2f}  DD={r['maxdd']*100:.1f}%  trades={r['trades']}  WR={r['winrate']*100:.1f}%  PF={r['pf']:.2f}")

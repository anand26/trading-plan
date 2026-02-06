"""Quick analysis of v4.0 trend filter backtest results."""
import pandas as pd
import json

df = pd.read_csv("backtest/trend_filter_results.csv")

rows = []
for _, r in df.iterrows():
    p = json.loads(r["ParametersJson"])
    sma_f = p.get("sma_fast_period", 50)
    sma_s = p.get("sma_slow_period", 200)
    rows.append({
        "Row": len(rows) + 1,
        "trend": p.get("trend_filter_enabled"),
        "sma": f"{sma_f}/{sma_s}",
        "lb": p.get("zscore_lookback"),
        "entry": p.get("entry_zscore"),
        "exit_z": p.get("exit_zscore"),
        "stop_z": p.get("stop_zscore"),
        "pos": p.get("position_size"),
        "sl": p.get("stop_loss_pct"),
        "halt": p.get("daily_loss_limit_pct"),
        "maxDD": p.get("max_drawdown_pct"),
        "dd_scl": p.get("drawdown_position_scale"),
        "vol_sc": p.get("enable_vol_scaling"),
        "Return": round(r["TotalReturn"] * 100, 2),
        "Sharpe": round(r["SharpeRatio"], 2),
        "DD": round(r["MaxDrawdown"] * 100, 1),
        "WR": round(r["WinRate"] * 100, 1),
        "PF": round(r["ProfitFactor"], 3),
        "Trades": int(r["TotalTrades"]),
    })

result = pd.DataFrame(rows)

# ──────────────────────────────────────────────
# 1. TREND FILTER: ON vs OFF
# ──────────────────────────────────────────────
print("=" * 80)
print("1. TREND FILTER: ON vs OFF (SMA 50/200, baseline params)")
print("=" * 80)

baseline_mask = (
    (result.lb == 46)
    & (result.entry == 1.5)
    & (result.exit_z == 0.32)
    & (result.stop_z == 3.0)
    & (result.pos == 0.57)
    & (result.sl == 0.02)
    & (result.sma == "50/200")
    & (result.halt == 0.02)
    & (result.maxDD == 0.25)
    & (result.dd_scl == 0.5)
    & (result.vol_sc == False)
)

on = result[baseline_mask & (result.trend == True)]
off = result[(result.trend == False)]

if len(on) > 0 and len(off) > 0:
    o = on.iloc[0]
    f = off.iloc[0]
    print(f"  Trend ON:  Return={o['Return']:>7.1f}%  Sharpe={o['Sharpe']:.2f}  DD={o['DD']:.1f}%  WR={o['WR']:.1f}%  PF={o['PF']:.3f}  Trades={o['Trades']}")
    print(f"  Trend OFF: Return={f['Return']:>7.1f}%  Sharpe={f['Sharpe']:.2f}  DD={f['DD']:.1f}%  WR={f['WR']:.1f}%  PF={f['PF']:.3f}  Trades={f['Trades']}")
print()

# ──────────────────────────────────────────────
# 2. SMA PERIOD COMPARISON
# ──────────────────────────────────────────────
print("=" * 80)
print("2. SMA PERIOD COMPARISON (all trend=ON, baseline Z-score params)")
print("=" * 80)
for sma_val in ["20/50", "50/150", "50/200"]:
    s = result[
        (result.sma == sma_val)
        & (result.trend == True)
        & (result.lb == 46)
        & (result.entry == 1.5)
        & (result.exit_z == 0.32)
        & (result.pos == 0.57)
        & (result.sl == 0.02)
    ]
    if len(s) > 0:
        r2 = s.iloc[0]
        print(f"  SMA {sma_val:>7s}: Return={r2['Return']:>7.1f}%  Sharpe={r2['Sharpe']:.2f}  DD={r2['DD']:.1f}%  WR={r2['WR']:.1f}%  PF={r2['PF']:.3f}  Trades={r2['Trades']}")
print()

# ──────────────────────────────────────────────
# 3. IDENTICAL RESULTS CLUSTER
# ──────────────────────────────────────────────
print("=" * 80)
print("3. IDENTICAL RESULTS CHECK")
print("=" * 80)
# Group by identical Return + Sharpe + Trades
grouped = result.groupby(["Return", "Sharpe", "Trades"]).size().reset_index(name="count")
grouped = grouped.sort_values("count", ascending=False)
for _, g in grouped.head(5).iterrows():
    if g["count"] > 1:
        cluster = result[(result.Return == g["Return"]) & (result.Sharpe == g["Sharpe"]) & (result.Trades == g["Trades"])]
        rows_list = cluster.Row.tolist()
        print(f"  {g['count']} runs identical: Return={g['Return']}%, Sharpe={g['Sharpe']}, Trades={g['Trades']}")
        print(f"    Rows: {rows_list}")
        # Show what varied
        for col in ["entry", "exit_z", "stop_z", "halt", "maxDD", "dd_scl", "vol_sc"]:
            vals = cluster[col].unique()
            if len(vals) > 1:
                print(f"    {col} varied: {sorted(vals)} → NO EFFECT")
print()

# ──────────────────────────────────────────────
# 4. STOP LOSS % IMPACT
# ──────────────────────────────────────────────
print("=" * 80)
print("4. STOP LOSS % IMPACT (trend=ON, SMA 50/200)")
print("=" * 80)
for sl in [0.015, 0.02, 0.025, 0.03]:
    s = result[
        (result.sl == sl)
        & (result.trend == True)
        & (result.sma == "50/200")
        & (result.lb == 46)
        & (result.entry == 1.5)
        & (result.exit_z == 0.32)
        & (result.pos == 0.57)
        & (result.halt == 0.02)
        & (result.maxDD == 0.25)
    ]
    if len(s) > 0:
        r2 = s.iloc[0]
        flag = " ← BEST" if r2["Sharpe"] == result[result.sma == "50/200"]["Sharpe"].max() else ""
        flag2 = " ← NEGATIVE" if r2["Return"] < 0 else ""
        print(f"  SL={sl*100:.1f}%: Return={r2['Return']:>7.2f}%  Sharpe={r2['Sharpe']:.2f}  PF={r2['PF']:.3f}  Trades={r2['Trades']}{flag}{flag2}")
print()

# ──────────────────────────────────────────────
# 5. LOOKBACK SENSITIVITY
# ──────────────────────────────────────────────
print("=" * 80)
print("5. LOOKBACK SENSITIVITY (trend=ON, SMA 50/200)")
print("=" * 80)
for lb in [44, 45, 46, 48, 50]:
    s = result[
        (result.lb == lb)
        & (result.trend == True)
        & (result.sma == "50/200")
        & (result.entry == 1.5)
        & (result.exit_z == 0.32)
        & (result.pos == 0.57)
        & (result.sl == 0.02)
        & (result.halt == 0.02)
        & (result.maxDD == 0.25)
        & (result.dd_scl == 0.5)
    ]
    if len(s) > 0:
        r2 = s.iloc[0]
        flag = " ← BEST" if r2["Sharpe"] >= 1.59 else ""
        print(f"  lb={lb}: Return={r2['Return']:>6.2f}%  Sharpe={r2['Sharpe']:.2f}  DD={r2['DD']:.1f}%  WR={r2['WR']:.1f}%  Trades={r2['Trades']}{flag}")
print()

# ──────────────────────────────────────────────
# 6. TOP 5 OVERALL
# ──────────────────────────────────────────────
print("=" * 80)
print("6. TOP 5 BY SHARPE (overall)")
print("=" * 80)
top5 = result.sort_values("Sharpe", ascending=False).head(5)
for _, r2 in top5.iterrows():
    tag = ""
    if r2["sma"] == "20/50":
        tag = " [SMA 20/50]"
    elif not r2["trend"]:
        tag = " [NO TREND]"
    print(
        f"  #{r2['Row']:>2d}  lb={r2['lb']} entry={r2['entry']} exit={r2['exit_z']} sl={r2['sl']} pos={r2['pos']} "
        f"sma={r2['sma']} → Return={r2['Return']:>7.1f}%  Sharpe={r2['Sharpe']:.2f}  DD={r2['DD']:.1f}%  PF={r2['PF']:.3f}{tag}"
    )
print()

# ──────────────────────────────────────────────
# 7. BOTTOM 3
# ──────────────────────────────────────────────
print("=" * 80)
print("7. WORST 3")
print("=" * 80)
bot3 = result.sort_values("Sharpe", ascending=True).head(3)
for _, r2 in bot3.iterrows():
    print(
        f"  #{r2['Row']:>2d}  sl={r2['sl']} stop_z={r2['stop_z']} "
        f"→ Return={r2['Return']:>7.2f}%  Sharpe={r2['Sharpe']:.2f}  PF={r2['PF']:.3f}"
    )

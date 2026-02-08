"""
Dynamic Backtest Results Analyzer
=================================
Automatically analyzes ALL strategy result CSVs in the results/ folder.
Supports: Daily Mean Reversion, Position Trend, Turtle, Pairs, and any future strategy.

Usage:
  python analyze-script.py                    # Analyze all CSVs in results/
  python analyze-script.py results/turtle_1.0.csv   # Analyze specific file
  Double-click to run (window stays open)
"""
import csv
import json
import os
import sys
import math
import atexit
from collections import defaultdict
from pathlib import Path

# ============================================================
# Keep window open on exit (for double-click runs)
# ============================================================
def wait_on_exit():
    print()
    print("=" * 60)
    try:
        input("Press Enter to exit...")
    except:
        import time
        time.sleep(10)

atexit.register(wait_on_exit)

# ============================================================
# CONFIGURATION
# ============================================================
RESULTS_DIR = Path(__file__).parent / "results"
IGNORE_DIRS = {"discard_old", "__pycache__"}

# Strategy display names
STRATEGY_NAMES = {
    "DAILY_MEAN_REVERSION": "Daily Mean Reversion (TQQQ)",
    "POSITION_TREND": "Position Trend Following (TQQQ)",
    "TURTLE_TQQQ": "Turtle Breakout (TQQQ)",
    "TQQQ_SCALPING": "TQQQ/SQQQ Pairs Scalping",
}

# Parameters to EXCLUDE from analysis (not tunable / metadata)
SKIP_PARAMS = {"algorithm_name", "_hash", "_optimization_run_id"}

# How to format parameter values in display
PCT_PARAMS = {
    "stop_loss_pct", "position_size", "trailing_activation_pct", "trailing_stop_pct",
    "partial_exit_pct", "partial_exit_fraction", "bull_allocation", "bear_allocation",
    "mixed_allocation", "rebalance_threshold", "max_drawdown_exit", "risk_per_trade",
    "max_position_pct", "vol_scale_factor", "vol_scale_threshold",
}


# ============================================================
# CORE: Load & Parse CSV
# ============================================================
def safe_float(val, default=0.0):
    """Convert to float, handling NULL, None, empty strings."""
    if val is None or str(val).strip().upper() in ("NULL", "", "NONE", "N/A"):
        return default
    try:
        return float(str(val).replace(",", "").replace("$", "").replace("%", ""))
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    """Convert to int, handling NULL, None, empty strings."""
    return int(safe_float(val, default))


def load_csv(filepath):
    """Load a backtest results CSV and return enriched rows."""
    rows = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for r in reader:
            params = json.loads(r.get("ParametersJson", "{}"))
            avg_win = safe_float(r.get("AverageWin"))
            avg_loss = safe_float(r.get("AverageLoss"))
            r_ratio = avg_win / avg_loss if avg_loss > 0 else 0

            row = {
                "ret": safe_float(r.get("TotalReturn")),
                "cagr": safe_float(r.get("CAGR")),
                "sharpe": safe_float(r.get("SharpeRatio")),
                "sortino": safe_float(r.get("SortinoRatio")),
                "calmar": safe_float(r.get("CalmarRatio")),
                "maxdd": safe_float(r.get("MaxDrawdown")),
                "vol": safe_float(r.get("Volatility")),
                "trades": safe_int(r.get("TotalTrades")),
                "wins": safe_int(r.get("WinningTrades")),
                "losses": safe_int(r.get("LosingTrades")),
                "winrate": safe_float(r.get("WinRate")),
                "pf": safe_float(r.get("ProfitFactor")),
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "r_ratio": r_ratio,
                "total_profit": safe_float(r.get("TotalProfit")),
                "total_loss": safe_float(r.get("TotalLoss")),
                "largest_win": safe_float(r.get("LargestWin")),
                "largest_loss": safe_float(r.get("LargestLoss")),
                "strategy_id": r.get("StrategyId", ""),
                "start_date": r.get("StartDate", ""),
                "end_date": r.get("EndDate", ""),
                "params": params,
            }

            # Store each param as a top-level key for easy access
            for k, v in params.items():
                if k not in SKIP_PARAMS:
                    row["p_" + k] = v

            rows.append(row)

    return rows


def detect_swept_params(rows):
    """Find parameters that were actually varied across backtests."""
    if not rows:
        return {}

    param_keys = [k for k in rows[0].get("params", {}).keys() if k not in SKIP_PARAMS]
    swept = {}

    for k in param_keys:
        values = set()
        for r in rows:
            v = r["params"].get(k)
            values.add(str(v))
        if len(values) > 1:
            # Get sorted unique raw values
            raw_values = sorted(set(r["params"].get(k) for r in rows), key=lambda x: (isinstance(x, bool), str(x)))
            swept[k] = raw_values

    return swept


def format_param_val(name, val):
    """Format a parameter value for display."""
    if isinstance(val, bool):
        return "ON" if val else "OFF"
    if isinstance(val, float) and name in PCT_PARAMS:
        return "{:.1f}%".format(val * 100)
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return "{:.2f}".format(val)
    return str(val)


# ============================================================
# ANALYSIS: Rankings
# ============================================================
def print_ranking_table(rows, swept_params, strategy_name):
    """Print main ranking table sorted by Sharpe."""
    rows_sorted = sorted(rows, key=lambda x: x["sharpe"], reverse=True)
    n = len(rows_sorted)

    # Determine which swept params to show as columns (max ~10 for readability)
    param_cols = list(swept_params.keys())[:10]

    # Build header
    hdr = "{:>3} {:>8} {:>7} {:>7} {:>8} {:>7} {:>6} {:>6} {:>6} {:>5}".format(
        "Rk", "Ret%", "CAGR%", "Sharpe", "Sortino", "MaxDD%", "Trades", "WR%", "PF", "R")
    for p in param_cols:
        short = abbreviate_param(p)
        hdr += " {:>7}".format(short)

    print(hdr)
    print("-" * len(hdr))

    for rank, r in enumerate(rows_sorted, 1):
        line = "{:>3} {:>7.2f}% {:>6.2f}% {:>7.4f} {:>8.4f} {:>6.1f}% {:>6} {:>5.1f} {:>6.3f} {:>5.2f}".format(
            rank, r["ret"] * 100, r["cagr"] * 100, r["sharpe"],
            r["sortino"], r["maxdd"] * 100, r["trades"],
            r["winrate"] * 100, r["pf"], r["r_ratio"])

        for p in param_cols:
            val = r["params"].get(p, "")
            fval = format_param_val(p, val)
            line += " {:>7}".format(fval)

        # Mark profitable
        if r["ret"] > 0:
            line += "  *"

        print(line)

    return rows_sorted


def abbreviate_param(name):
    """Create short column header from parameter name."""
    abbrevs = {
        "zscore_lookback": "LB",
        "entry_zscore": "EntZ",
        "exit_zscore": "ExZ",
        "exit_target_zscore": "ExTgt",
        "stop_zscore": "StpZ",
        "stop_loss_pct": "Stop%",
        "position_size": "Pos%",
        "max_hold_days": "Hold",
        "max_hold_minutes": "HoldM",
        "min_bars_between": "MinB",
        "min_days_between": "MinD",
        "trailing_stop_atr": "TrATR",
        "trailing_activation_pct": "TrAct",
        "trailing_stop_pct": "TrW",
        "atr_period": "ATR",
        "use_rsi_filter": "RSI?",
        "rsi_period": "RSIp",
        "rsi_oversold": "RSIlo",
        "rsi_overbought": "RSIhi",
        "use_vol_scaling": "VolS?",
        "vol_scale_threshold": "VSThr",
        "vol_scale_factor": "VSFac",
        "sma_fast": "SMAf",
        "sma_slow": "SMAs",
        "bull_allocation": "Bull%",
        "bear_allocation": "Bear%",
        "use_cash_zone": "Cash?",
        "mixed_allocation": "Mix%",
        "mixed_instrument": "MixIn",
        "rebalance_threshold": "Rebal",
        "max_drawdown_exit": "DDEx",
        "confirmation_days": "Conf",
        "entry_period": "Entry",
        "exit_period": "Exit",
        "risk_per_trade": "Risk",
        "atr_stop_multiple": "ATRx",
        "leverage_factor": "Lev",
        "max_units": "Units",
        "pyramid_atr_step": "Pyram",
        "max_position_pct": "MaxP%",
        "use_qqq_filter": "QQQ?",
        "exit_confirmation_bars": "ExCnf",
        "enable_partial_exit": "Part?",
        "partial_exit_pct": "PP%",
        "partial_exit_fraction": "PFrac",
    }
    return abbrevs.get(name, name[:7])


# ============================================================
# ANALYSIS: Summary Statistics
# ============================================================
def print_summary_stats(rows):
    """Print summary statistics."""
    n = len(rows)
    if n == 0:
        print("  No data")
        return

    rets = sorted(r["ret"] for r in rows)
    sharpes = sorted(r["sharpe"] for r in rows)
    dds = sorted(r["maxdd"] for r in rows)
    r_ratios = sorted(r["r_ratio"] for r in rows)
    profitable = [r for r in rows if r["ret"] > 0]

    median_idx = n // 2
    print("  Total combinations:   {}".format(n))
    print("  Profitable:           {}/{} ({:.0f}%)".format(len(profitable), n, len(profitable) / n * 100))
    print("  Returns:    min={:>8.2f}%   max={:>8.2f}%   median={:>8.2f}%".format(
        rets[0] * 100, rets[-1] * 100, rets[median_idx] * 100))
    print("  Sharpe:     min={:>8.4f}   max={:>8.4f}   median={:>8.4f}".format(
        sharpes[0], sharpes[-1], sharpes[median_idx]))
    print("  MaxDD:      min={:>7.1f}%    max={:>7.1f}%".format(dds[0] * 100, dds[-1] * 100))
    print("  R-Ratio:    min={:>8.2f}   max={:>8.2f}   median={:>8.2f}".format(
        r_ratios[0], r_ratios[-1], r_ratios[median_idx]))

    # Average trade-level edge
    avg_edges = []
    for r in rows:
        if r["trades"] > 0:
            edge = r["avg_win"] * r["winrate"] - r["avg_loss"] * (1 - r["winrate"])
            avg_edges.append(edge)
    if avg_edges:
        print("  Avg Edge/Trade: ${:.2f}".format(sum(avg_edges) / len(avg_edges)))


# ============================================================
# ANALYSIS: Parameter Impact (one-at-a-time)
# ============================================================
def print_parameter_impact(rows, swept_params):
    """For each swept parameter, show how different values affect performance."""
    if not swept_params:
        print("  No parameters were varied.")
        return

    for param_name, unique_vals in swept_params.items():
        short = abbreviate_param(param_name)
        print()
        print("  " + "-" * 70)
        print("  {} ({} values tested)".format(param_name, len(unique_vals)))
        print("  " + "-" * 70)

        for val in unique_vals:
            matching = [r for r in rows if r["params"].get(param_name) == val]
            if not matching:
                continue

            avg_ret = sum(r["ret"] for r in matching) / len(matching)
            avg_sharpe = sum(r["sharpe"] for r in matching) / len(matching)
            avg_dd = sum(r["maxdd"] for r in matching) / len(matching)
            avg_wr = sum(r["winrate"] for r in matching) / len(matching)
            avg_rr = sum(r["r_ratio"] for r in matching) / len(matching)
            avg_trades = sum(r["trades"] for r in matching) / len(matching)

            fval = format_param_val(param_name, val)
            print("    {:>7}={:<8}  n={:>2}  "
                  "avgRet={:>7.2f}%  avgSharpe={:>7.4f}  "
                  "avgDD={:>5.1f}%  avgWR={:>5.1f}%  "
                  "avgR={:>5.2f}  avgTrades={:>5.0f}".format(
                      short, fval, len(matching),
                      avg_ret * 100, avg_sharpe,
                      avg_dd * 100, avg_wr * 100,
                      avg_rr, avg_trades))


# ============================================================
# ANALYSIS: Correlation with Sharpe
# ============================================================
def print_correlation_analysis(rows, swept_params):
    """Show which parameters have the strongest correlation with Sharpe ratio."""
    if len(rows) < 5:
        print("  Too few data points for correlation analysis.")
        return

    sharpe_vals = [r["sharpe"] for r in rows]

    correlations = []
    for param_name, unique_vals in swept_params.items():
        # Skip non-numeric params
        if any(isinstance(v, (bool, str)) for v in unique_vals):
            continue

        param_vals = [float(r["params"].get(param_name, 0)) for r in rows]

        # Calculate Pearson correlation manually (no external deps)
        n = len(param_vals)
        if n < 3 or len(set(param_vals)) < 2:
            continue

        mean_x = sum(param_vals) / n
        mean_y = sum(sharpe_vals) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(param_vals, sharpe_vals)) / n
        std_x = math.sqrt(sum((x - mean_x) ** 2 for x in param_vals) / n)
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in sharpe_vals) / n)

        if std_x > 0 and std_y > 0:
            corr = cov / (std_x * std_y)
            correlations.append((param_name, corr))

    if not correlations:
        print("  No numeric parameters to correlate.")
        return

    # Sort by absolute correlation
    correlations.sort(key=lambda x: abs(x[1]), reverse=True)

    for param_name, corr in correlations:
        if abs(corr) > 0.1:
            direction = "higher is better" if corr > 0.1 else "lower is better"
        else:
            direction = "~ minimal impact"

        bar_len = int(abs(corr) * 20)
        bar = "#" * bar_len
        print("    {:>7} ({:.<25}): corr={:>+.3f} {:<10} {}".format(
            abbreviate_param(param_name), param_name, corr, bar, direction))


# ============================================================
# ANALYSIS: Top/Bottom Rankings
# ============================================================
def print_top_bottom(rows, swept_params, metric, label, top_n=5, reverse=True):
    """Print top N rows by a given metric."""
    sorted_rows = sorted(rows, key=lambda x: x[metric], reverse=reverse)

    param_cols = list(swept_params.keys())[:8]

    for i, r in enumerate(sorted_rows[:top_n], 1):
        # Build param config string
        cfg_parts = []
        for p in param_cols:
            val = r["params"].get(p)
            if val is not None:
                cfg_parts.append("{}={}".format(abbreviate_param(p), format_param_val(p, val)))
        cfg = ", ".join(cfg_parts)

        if metric == "r_ratio":
            print("  #{:>2}: R={:.2f}  avgW=${:.1f}  avgL=${:.1f}  "
                  "ret={:.2f}%  Sharpe={:.4f}  WR={:.1f}%".format(
                      i, r["r_ratio"], r["avg_win"], r["avg_loss"],
                      r["ret"] * 100, r["sharpe"], r["winrate"] * 100))
        elif metric == "ret":
            print("  #{:>2}: ret={:.2f}%  Sharpe={:.4f}  DD={:.1f}%  "
                  "trades={}  R={:.2f}  PF={:.3f}".format(
                      i, r["ret"] * 100, r["sharpe"], r["maxdd"] * 100,
                      r["trades"], r["r_ratio"], r["pf"]))
        elif metric == "calmar":
            print("  #{:>2}: Calmar={:.4f}  ret={:.2f}%  DD={:.1f}%  "
                  "Sharpe={:.4f}  trades={}".format(
                      i, r["calmar"], r["ret"] * 100, r["maxdd"] * 100,
                      r["sharpe"], r["trades"]))
        else:  # sharpe
            print("  #{:>2}: Sharpe={:.4f}  ret={:.2f}%  DD={:.1f}%  "
                  "trades={}  WR={:.1f}%  R={:.2f}  PF={:.3f}".format(
                      i, r["sharpe"], r["ret"] * 100, r["maxdd"] * 100,
                      r["trades"], r["winrate"] * 100, r["r_ratio"], r["pf"]))

        # Print config on next line for readability
        print("        [{}]".format(cfg))


# ============================================================
# ANALYSIS: Best Combo Recommendation
# ============================================================
def print_recommendation(rows, swept_params):
    """Print the recommended best parameter combination."""
    if not rows:
        return

    # Score each row: weighted combination of normalized metrics
    # Higher is better for: ret, sharpe, sortino, calmar, winrate, pf, r_ratio
    # Lower is better for: maxdd
    metrics = {
        "sharpe":  {"weight": 0.30, "higher_better": True},
        "calmar":  {"weight": 0.20, "higher_better": True},
        "ret":     {"weight": 0.15, "higher_better": True},
        "r_ratio": {"weight": 0.10, "higher_better": True},
        "pf":      {"weight": 0.10, "higher_better": True},
        "winrate": {"weight": 0.10, "higher_better": True},
        "maxdd":   {"weight": 0.05, "higher_better": False},
    }

    # Normalize each metric to 0-1
    for m in metrics:
        vals = [r[m] for r in rows]
        min_v, max_v = min(vals), max(vals)
        rng = max_v - min_v if max_v != min_v else 1
        for r in rows:
            norm = (r[m] - min_v) / rng
            if not metrics[m]["higher_better"]:
                norm = 1 - norm
            r["_norm_" + m] = norm

    # Calculate composite score
    for r in rows:
        r["_score"] = sum(r["_norm_" + m] * info["weight"] for m, info in metrics.items())

    best = max(rows, key=lambda x: x["_score"])

    print("  Composite Score: {:.4f}".format(best["_score"]))
    print("  Return: {:.2f}%  |  CAGR: {:.2f}%  |  Sharpe: {:.4f}".format(
        best["ret"] * 100, best["cagr"] * 100, best["sharpe"]))
    print("  Sortino: {:.4f}  |  Calmar: {:.4f}  |  MaxDD: {:.1f}%".format(
        best["sortino"], best["calmar"], best["maxdd"] * 100))
    print("  Trades: {}  |  WinRate: {:.1f}%  |  PF: {:.3f}  |  R: {:.2f}".format(
        best["trades"], best["winrate"] * 100, best["pf"], best["r_ratio"]))
    print("  AvgWin: ${:.2f}  |  AvgLoss: ${:.2f}".format(best["avg_win"], best["avg_loss"]))
    print()
    print("  Recommended Parameters:")
    for p in swept_params:
        val = best["params"].get(p)
        if val is not None:
            fval = format_param_val(p, val)
            print("    {:.<40} {}".format(p + " ", fval))


# ============================================================
# ANALYSIS: Cross-Strategy Comparison
# ============================================================
def print_cross_strategy_comparison(all_results):
    """Compare best result from each strategy side by side."""
    if len(all_results) < 2:
        return

    print()
    print("=" * 100)
    print("CROSS-STRATEGY COMPARISON (Best by Sharpe from each)")
    print("=" * 100)

    # Header
    strats = list(all_results.keys())
    col_w = 20
    hdr = "{:<20}".format("Metric")
    for s in strats:
        display = s[:col_w]
        hdr += " {:>{}}".format(display, col_w)
    print(hdr)
    print("-" * len(hdr))

    # Get best by Sharpe for each
    bests = {}
    for sname, rows in all_results.items():
        bests[sname] = max(rows, key=lambda x: x["sharpe"])

    # Print comparison rows
    metrics_display = [
        ("Strategy", lambda r: STRATEGY_NAMES.get(r["strategy_id"], r["strategy_id"])[:col_w]),
        ("Return %", lambda r: "{:.2f}%".format(r["ret"] * 100)),
        ("CAGR %", lambda r: "{:.2f}%".format(r["cagr"] * 100)),
        ("Sharpe", lambda r: "{:.4f}".format(r["sharpe"])),
        ("Sortino", lambda r: "{:.4f}".format(r["sortino"])),
        ("Calmar", lambda r: "{:.4f}".format(r["calmar"])),
        ("Max DD %", lambda r: "{:.1f}%".format(r["maxdd"] * 100)),
        ("Volatility %", lambda r: "{:.2f}%".format(r["vol"] * 100) if r["vol"] else "N/A"),
        ("Total Trades", lambda r: str(r["trades"])),
        ("Win Rate %", lambda r: "{:.1f}%".format(r["winrate"] * 100)),
        ("Profit Factor", lambda r: "{:.3f}".format(r["pf"])),
        ("R-Ratio", lambda r: "{:.2f}".format(r["r_ratio"])),
        ("Avg Win $", lambda r: "${:.2f}".format(r["avg_win"])),
        ("Avg Loss $", lambda r: "${:.2f}".format(r["avg_loss"])),
    ]

    for label, fmt_fn in metrics_display:
        line = "  {:<20}".format(label)
        for sname in strats:
            val = fmt_fn(bests[sname])
            line += " {:>{}}".format(val, col_w)
        print(line)

    # Highlight winner
    print()
    best_overall_name = max(strats, key=lambda s: bests[s]["sharpe"])
    best_overall = bests[best_overall_name]
    print("  >>> BEST STRATEGY BY SHARPE: {} (Sharpe={:.4f}, Return={:.2f}%)".format(
        best_overall_name, best_overall["sharpe"], best_overall["ret"] * 100))


# ============================================================
# MAIN: Analyze a single strategy
# ============================================================
def analyze_strategy(filepath, rows):
    """Run full analysis for one strategy file."""
    if not rows:
        print("  [EMPTY] No data in {}".format(filepath.name))
        return {}

    strategy_id = rows[0].get("strategy_id", "UNKNOWN")
    strategy_name = STRATEGY_NAMES.get(strategy_id, strategy_id)
    start_date = rows[0].get("start_date", "?")
    end_date = rows[0].get("end_date", "?")
    swept_params = detect_swept_params(rows)

    width = 100
    print()
    print("#" * width)
    print("#  {}".format(strategy_name))
    print("#  File: {}  |  {} combinations  |  {} to {}".format(
        filepath.name, len(rows), start_date, end_date))
    print("#  Swept: {}".format(", ".join(swept_params.keys())))
    print("#" * width)

    # 1. Main Ranking Table
    print()
    print("=" * width)
    print("RANKING TABLE (sorted by Sharpe)")
    print("=" * width)
    sorted_rows = print_ranking_table(rows, swept_params, strategy_name)

    # 2. Summary Stats
    print()
    print("=" * width)
    print("SUMMARY STATISTICS")
    print("=" * width)
    print_summary_stats(rows)

    # 3. Parameter Impact Analysis
    print()
    print("=" * width)
    print("PARAMETER IMPACT ANALYSIS (average metrics per parameter value)")
    print("=" * width)
    print_parameter_impact(rows, swept_params)

    # 4. Correlation Analysis
    print()
    print("=" * width)
    print("PARAMETER CORRELATION WITH SHARPE RATIO")
    print("=" * width)
    print_correlation_analysis(rows, swept_params)

    # 5. Top Rankings
    for metric, label in [("sharpe", "Sharpe Ratio"), ("ret", "Total Return"),
                           ("calmar", "Calmar Ratio"), ("r_ratio", "R-Ratio (AvgWin/AvgLoss)")]:
        print()
        print("=" * width)
        print("TOP 5 BY {}".format(label.upper()))
        print("=" * width)
        print_top_bottom(rows, swept_params, metric, label, top_n=5)

    # 6. Bottom 3
    print()
    print("=" * width)
    print("BOTTOM 3 (worst performers - what to avoid)")
    print("=" * width)
    print_top_bottom(rows, swept_params, "sharpe", "Sharpe", top_n=3, reverse=False)

    # 7. Recommendation
    print()
    print("=" * width)
    print("*** RECOMMENDED BEST COMBINATION ***")
    print("=" * width)
    print_recommendation(rows, swept_params)

    return {"strategy_id": strategy_id, "rows": rows, "swept_params": swept_params}


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def main():
    # Determine which files to analyze
    if len(sys.argv) > 1:
        # Specific file(s) passed as arguments
        csv_files = [Path(f) for f in sys.argv[1:] if f.endswith(".csv")]
    else:
        # Auto-discover all CSVs in results/ (ignore subdirectories)
        csv_files = sorted(RESULTS_DIR.glob("*.csv"))

    if not csv_files:
        print("[ERROR] No CSV files found in {}".format(RESULTS_DIR))
        print("  Put your backtest result CSVs in: {}".format(RESULTS_DIR))
        return

    print()
    print("=" * 80)
    print("  DYNAMIC BACKTEST RESULTS ANALYZER")
    print("  Found {} strategy file(s)".format(len(csv_files)))
    print("=" * 80)
    print()
    for f in csv_files:
        print("  -> {}".format(f.name))

    # Analyze each strategy
    all_results = {}
    for filepath in csv_files:
        try:
            rows = load_csv(filepath)
            if rows:
                result = analyze_strategy(filepath, rows)
                if result:
                    all_results[filepath.stem] = rows
        except Exception as e:
            print("\n[ERROR] Failed to analyze {}: {}".format(filepath.name, e))
            import traceback
            traceback.print_exc()

    # Cross-strategy comparison (if multiple)
    if len(all_results) >= 2:
        print_cross_strategy_comparison(all_results)

    # Final summary
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("  Strategies analyzed: {}".format(len(all_results)))
    for name, rows in all_results.items():
        best = max(rows, key=lambda x: x["sharpe"])
        print("  {}: best Sharpe={:.4f}, ret={:.2f}%, DD={:.1f}%".format(
            name, best["sharpe"], best["ret"] * 100, best["maxdd"] * 100))


if __name__ == "__main__":
    main()

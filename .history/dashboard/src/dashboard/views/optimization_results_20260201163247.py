"""
Optimization Results View
=========================
Dashboard view for analyzing parameter optimization results.

Features:
- Run optimization from CSV
- Summary statistics
- Parameter impact analysis
- Heatmap visualizations
- Filterable results table
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional
from datetime import datetime, date
import subprocess
import sys
import os
from pathlib import Path
import threading
import queue
import time

from dashboard.database import (
    get_optimization_runs,
    get_optimization_results,
    get_parameter_impact_analysis,
    get_top_parameter_combinations,
    get_parameter_heatmap_data,
    get_optimization_summary,
)


def render_optimization_results():
    """Render the optimization results view."""
    st.title("📊 Parameter Optimization")
    st.caption("Run parameter sweeps and analyze results")
    
    # Sidebar filters
    with st.sidebar:
        st.subheader("🔍 Filters")
        
        # Get available optimization runs
        runs_df = get_optimization_runs()
        
        if not runs_df.empty:
            run_options = ["All Runs"] + runs_df['RunId'].tolist()
            selected_run = st.selectbox(
                "Optimization Run",
                options=run_options,
                index=0,
                help="Filter results by optimization run"
            )
            run_id = None if selected_run == "All Runs" else selected_run
        else:
            run_id = None
            st.info("No optimization runs found")
        
        st.divider()
        
        # Performance filters
        st.subheader("Performance Filters")
        
        min_sharpe = st.number_input(
            "Min Sharpe Ratio",
            min_value=-5.0,
            max_value=10.0,
            value=-5.0,
            step=0.1,
            help="Filter by minimum Sharpe ratio"
        )
        min_sharpe = None if min_sharpe <= -5.0 else min_sharpe
        
        max_drawdown = st.number_input(
            "Max Drawdown %",
            min_value=0.0,
            max_value=100.0,
            value=100.0,
            step=1.0,
            help="Filter by maximum drawdown percentage"
        )
        max_drawdown = None if max_drawdown >= 100.0 else max_drawdown / 100
        
        min_trades = st.number_input(
            "Min Trades",
            min_value=0,
            max_value=1000,
            value=0,
            step=1,
            help="Filter by minimum number of trades"
        )
        min_trades = None if min_trades == 0 else min_trades
        
        min_win_rate = st.number_input(
            "Min Win Rate %",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            help="Filter by minimum win rate"
        )
        min_win_rate = None if min_win_rate == 0.0 else min_win_rate / 100
    
    # Main content tabs
    tab0, tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Run Optimization",
        "📈 Summary",
        "🎯 Parameter Impact",
        "🗺️ Heatmaps",
        "📋 Raw Results"
    ])
    
    # Tab 0: Run Optimization
    with tab0:
        render_run_optimization_tab()
    
    # Tab 1: Summary
    with tab1:
        render_summary_tab(run_id)
    
    # Tab 2: Parameter Impact
    with tab2:
        render_parameter_impact_tab(run_id)
    
    # Tab 3: Heatmaps
    with tab3:
        render_heatmap_tab(run_id)
    
    # Tab 4: Raw Results
    with tab4:
        render_raw_results_tab(run_id, min_sharpe, max_drawdown, min_trades, min_win_rate)


def render_run_optimization_tab():
    """Render the Run Optimization tab for executing parameter sweeps."""
    st.subheader("🚀 Run Parameter Optimization")
    st.caption("Load parameter combinations from CSV and run batch backtests")
    
    # Initialize session state
    if 'opt_running' not in st.session_state:
        st.session_state.opt_running = False
    if 'opt_output' not in st.session_state:
        st.session_state.opt_output = []
    if 'opt_progress' not in st.session_state:
        st.session_state.opt_progress = 0
    if 'opt_total' not in st.session_state:
        st.session_state.opt_total = 0
    
    # Configuration section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📁 Parameter File")
        
        # Option 1: Use default file
        # Option 2: Upload custom file
        file_source = st.radio(
            "Parameter Source",
            options=["Use Default (parameter_combinations.csv)", "Upload Custom CSV"],
            horizontal=True,
            label_visibility="collapsed"
        )
        
        csv_path = None
        uploaded_df = None
        
        if file_source == "Use Default (parameter_combinations.csv)":
            # Get the default CSV path
            base_path = Path(__file__).parent.parent.parent.parent.parent  # Go up to trading_plan
            default_csv = base_path / "backtest" / "parameter_combinations.csv"
            
            if default_csv.exists():
                csv_path = str(default_csv)
                st.success(f"✓ Default file found: `parameter_combinations.csv`")
                
                # Show preview
                try:
                    preview_df = pd.read_csv(default_csv)
                    st.caption(f"**{len(preview_df)} combinations** in file")
                    with st.expander("Preview Parameters", expanded=False):
                        st.dataframe(preview_df.head(10), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Error reading file: {e}")
            else:
                st.warning("Default file not found. Please upload a CSV file.")
        else:
            uploaded_file = st.file_uploader(
                "Upload Parameter CSV",
                type=['csv'],
                help="CSV with columns: rsi_period, rsi_oversold, rsi_overbought, bb_period, bb_std_dev, stop_loss_pct, take_profit_pct"
            )
            
            if uploaded_file:
                try:
                    uploaded_df = pd.read_csv(uploaded_file)
                    st.success(f"✓ Loaded {len(uploaded_df)} combinations")
                    
                    with st.expander("Preview Parameters", expanded=False):
                        st.dataframe(uploaded_df.head(10), use_container_width=True, hide_index=True)
                    
                    # Save to temp file for optimizer
                    temp_path = Path(__file__).parent.parent.parent.parent.parent / "backtest" / "temp_params.csv"
                    uploaded_df.to_csv(temp_path, index=False)
                    csv_path = str(temp_path)
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")
    
    with col2:
        st.markdown("### 📅 Date Range")
        
        start_date = st.date_input(
            "Start Date",
            value=date(2026, 1, 2),
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31),
            help="Backtest start date"
        )
        
        end_date = st.date_input(
            "End Date",
            value=date(2026, 1, 13),
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31),
            help="Backtest end date"
        )
        
        if end_date <= start_date:
            st.error("End date must be after start date")
        
        st.markdown("### ⚙️ Options")
        
        resume_mode = st.checkbox(
            "Resume Mode",
            value=True,
            help="Skip already-completed combinations"
        )
    
    st.divider()
    
    # Run button and status
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        can_run = csv_path is not None and end_date > start_date
        run_clicked = st.button(
            "▶️ Start Optimization",
            type="primary",
            disabled=not can_run,
            use_container_width=True
        )
    
    with col2:
        if st.session_state.opt_progress > 0:
            st.success(f"✅ Last run: {st.session_state.opt_progress} backtests completed")
    
    with col3:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Run optimization with real-time status display
    if run_clicked and can_run:
        run_optimization_with_status(
            csv_path=csv_path,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            resume=resume_mode
        )
    
    # Quick actions
    st.divider()
    st.markdown("### 📝 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Create New CSV**")
        st.caption("Generate a parameter grid CSV")
        if st.button("📄 Generate Template", use_container_width=True):
            template_df = generate_parameter_template()
            csv_data = template_df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download Template",
                data=csv_data,
                file_name="parameter_template.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col2:
        st.markdown("**View History**")
        st.caption("See past optimization runs")
        runs_df = get_optimization_runs()
        if not runs_df.empty:
            st.dataframe(
                runs_df[['RunId', 'Status', 'CompletedCombinations', 'TotalCombinations']].head(5),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No previous runs")
    
    with col3:
        st.markdown("**Refresh Results**")
        st.caption("Reload optimization data")
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


def run_optimization_with_status(csv_path: str, start_date: str, end_date: str, resume: bool = True):
    """Run optimization with real-time status updates using st.status."""
    import subprocess
    import sys
    
    # Get paths
    base_path = Path(__file__).parent.parent.parent.parent.parent  # trading_plan
    optimizer_script = base_path / "backtest" / "parameter_optimizer.py"
    python_exe = sys.executable
    
    # Build command
    cmd = [
        python_exe,
        str(optimizer_script),
        "--mode", "csv",
        "--csv-file", csv_path,
        "--start", start_date,
        "--end", end_date,
    ]
    
    if not resume:
        cmd.append("--no-resume")
    
    # Use st.status for real-time updates
    with st.status("🚀 Running Parameter Optimization...", expanded=True) as status:
        progress_text = st.empty()
        output_area = st.empty()
        progress_bar = st.progress(0)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(base_path),
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )
            
            output_lines = []
            current = 0
            total = 50  # Default
            
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue
                
                output_lines.append(line)
                
                # Parse progress from output like "[1/50] Testing:"
                if "/" in line and ("[" in line):
                    try:
                        bracket_content = line.split("]")[0].split("[")[-1]
                        if "/" in bracket_content:
                            parts = bracket_content.split("/")
                            current = int(parts[0])
                            total = int(parts[1])
                            progress_bar.progress(current / total)
                            progress_text.markdown(f"**Progress: {current}/{total}** ({100*current/total:.0f}%)")
                    except:
                        pass
                
                # Show last 20 lines of output
                output_area.code("\n".join(output_lines[-20:]), language="text")
                
                # Check for completion markers
                if "[OK]" in line or "[FAIL]" in line:
                    st.session_state.opt_progress = current
            
            process.wait()
            
            if process.returncode == 0:
                status.update(label="✅ Optimization Complete!", state="complete", expanded=False)
                st.session_state.opt_progress = total
                st.balloons()
            else:
                status.update(label=f"❌ Optimization Failed (code {process.returncode})", state="error")
                
        except Exception as e:
            status.update(label=f"❌ Error: {str(e)}", state="error")
    
    # Offer to view results
    st.success(f"Completed! View results in the **Summary** or **Raw Results** tabs.")
    if st.button("🔄 Refresh to see results"):
        st.cache_data.clear()
        st.rerun()


def generate_parameter_template() -> pd.DataFrame:
    """Generate a template CSV with parameter combinations."""
    # Create a small grid of common parameters
    import itertools
    
    params = {
        'rsi_period': [14],
        'rsi_oversold': [25, 30, 35],
        'rsi_overbought': [65, 70, 75],
        'bb_period': [20],
        'bb_std_dev': [1.5, 2.0, 2.5],
        'stop_loss_pct': [0.015, 0.02, 0.025],
        'take_profit_pct': [0.03],
    }
    
    # Generate combinations
    keys = list(params.keys())
    combinations = list(itertools.product(*params.values()))
    
    return pd.DataFrame(combinations, columns=keys)


def render_summary_tab(run_id: Optional[str]):
    """Render the summary statistics tab."""
    st.subheader("Optimization Summary")
    
    # Get summary stats
    summary = get_optimization_summary(run_id)
    
    if not summary or summary.get('total_backtests', 0) == 0:
        st.warning("No optimization results found. Run parameter optimization first.")
        st.code("""
# Run from command line:
python backtest/parameter_optimizer.py --mode grid --start 2026-01-02 --end 2026-01-13

# Or load from CSV:
from backtest.parameter_optimizer import ParameterOptimizer
optimizer = ParameterOptimizer()
combinations = optimizer.load_combinations_from_csv("backtest/parameter_combinations.csv")
optimizer.run_batch_optimization(combinations)
        """)
        return
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Backtests",
            f"{summary.get('total_backtests', 0):,}",
            help="Number of parameter combinations tested"
        )
    
    with col2:
        profitable = summary.get('profitable_runs', 0)
        total = summary.get('total_backtests', 1)
        pct = (profitable / total) * 100 if total > 0 else 0
        st.metric(
            "Profitable Runs",
            f"{profitable:,} ({pct:.1f}%)",
            help="Runs with positive return"
        )
    
    with col3:
        good_sharpe = summary.get('good_sharpe_runs', 0)
        pct = (good_sharpe / total) * 100 if total > 0 else 0
        st.metric(
            "Good Sharpe (>1)",
            f"{good_sharpe:,} ({pct:.1f}%)",
            help="Runs with Sharpe ratio > 1"
        )
    
    with col4:
        st.metric(
            "Total Trades",
            f"{summary.get('total_trades', 0):,}",
            help="Combined trades across all runs"
        )
    
    st.divider()
    
    # Performance distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Return Distribution")
        st.metric("Average Return", f"{summary.get('avg_return', 0)*100:.2f}%")
        st.metric("Best Return", f"{summary.get('best_return', 0)*100:.2f}%", delta="Best")
        st.metric("Worst Return", f"{summary.get('worst_return', 0)*100:.2f}%", delta="Worst", delta_color="inverse")
    
    with col2:
        st.markdown("### Risk Metrics")
        st.metric("Average Sharpe", f"{summary.get('avg_sharpe', 0):.2f}")
        st.metric("Best Sharpe", f"{summary.get('best_sharpe', 0):.2f}", delta="Best")
        st.metric("Average Drawdown", f"{summary.get('avg_drawdown', 0)*100:.2f}%")
    
    st.divider()
    
    # Top combinations table
    st.subheader("🏆 Top Performing Combinations")
    
    metric_options = {
        "sharpe": "Sharpe Ratio",
        "return": "Total Return",
        "win_rate": "Win Rate",
        "profit_factor": "Profit Factor"
    }
    
    metric_choice = st.selectbox(
        "Rank by",
        options=list(metric_options.keys()),
        format_func=lambda x: metric_options[x]
    )
    
    top_df = get_top_parameter_combinations(top_n=10, metric=metric_choice, run_id=run_id)
    
    if not top_df.empty:
        # Format for display
        display_df = top_df[[
            'rsi_period', 'rsi_oversold', 'rsi_overbought',
            'bb_period', 'bb_std_dev', 'stop_loss_pct',
            'TotalReturn', 'SharpeRatio', 'WinRate', 'MaxDrawdown', 'TotalTrades'
        ]].copy()
        
        display_df.columns = [
            'RSI Period', 'RSI Oversold', 'RSI Overbought',
            'BB Period', 'BB StdDev', 'Stop Loss %',
            'Return', 'Sharpe', 'Win Rate', 'Max DD', 'Trades'
        ]
        
        # Format percentages
        display_df['Return'] = display_df['Return'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A")
        display_df['Win Rate'] = display_df['Win Rate'].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
        display_df['Max DD'] = display_df['Max DD'].apply(lambda x: f"{abs(x)*100:.2f}%" if pd.notna(x) else "N/A")
        display_df['Stop Loss %'] = display_df['Stop Loss %'].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
        display_df['Sharpe'] = display_df['Sharpe'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No results to display")


def render_parameter_impact_tab(run_id: Optional[str]):
    """Render the parameter impact analysis tab."""
    st.subheader("Parameter Impact Analysis")
    st.caption("See how each parameter value affects performance")
    
    # Parameter selector
    param_options = {
        'rsi_period': 'RSI Period',
        'rsi_oversold': 'RSI Oversold',
        'rsi_overbought': 'RSI Overbought',
        'bb_period': 'BB Period',
        'bb_std_dev': 'BB Standard Deviation',
        'stop_loss_pct': 'Stop Loss %',
        'take_profit_pct': 'Take Profit %',
    }
    
    selected_param = st.selectbox(
        "Select Parameter",
        options=list(param_options.keys()),
        format_func=lambda x: param_options[x]
    )
    
    # Get impact data
    impact_df = get_parameter_impact_analysis(selected_param, run_id)
    
    if impact_df.empty:
        st.warning(f"No data available for {param_options[selected_param]}")
        return
    
    # Display metrics by value
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Bar chart of Sharpe by parameter value
        fig = px.bar(
            impact_df,
            x='ParamValue',
            y='AvgSharpe',
            title=f"Average Sharpe Ratio by {param_options[selected_param]}",
            labels={'ParamValue': param_options[selected_param], 'AvgSharpe': 'Avg Sharpe'},
            color='AvgSharpe',
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Best Value")
        best_row = impact_df.loc[impact_df['AvgSharpe'].idxmax()]
        param_val = best_row['ParamValue']
        st.metric(
            f"Optimal {param_options[selected_param]}",
            f"{param_val:.2f}" if isinstance(param_val, (int, float)) else str(param_val)
        )
        st.metric("Avg Sharpe", f"{float(best_row['AvgSharpe']):.2f}")
        st.metric("Avg Return", f"{float(best_row['AvgReturn'])*100:.2f}%")
        st.metric("Sample Count", f"{int(best_row['SampleCount'])}")
    
    # Return vs Sharpe scatter
    fig2 = px.scatter(
        impact_df,
        x='AvgReturn',
        y='AvgSharpe',
        size='SampleCount',
        color='ParamValue',
        title=f"Return vs Sharpe by {param_options[selected_param]}",
        labels={
            'AvgReturn': 'Average Return',
            'AvgSharpe': 'Average Sharpe',
            'ParamValue': param_options[selected_param]
        },
        hover_data=['AvgWinRate', 'AvgDrawdown']
    )
    st.plotly_chart(fig2, use_container_width=True)
    
    # Detailed table
    st.markdown("### Detailed Statistics")
    display_impact = impact_df.copy()
    display_impact.columns = [
        'Value', 'Samples', 'Avg Return', 'Avg Sharpe', 'Avg Win Rate',
        'Avg Drawdown', 'Avg Trades', 'Avg PF', 'Min Return', 'Max Return',
        'Min Sharpe', 'Max Sharpe'
    ]
    
    # Format
    for col in ['Avg Return', 'Min Return', 'Max Return', 'Avg Drawdown']:
        display_impact[col] = display_impact[col].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A")
    display_impact['Avg Win Rate'] = display_impact['Avg Win Rate'].apply(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")
    
    st.dataframe(display_impact, use_container_width=True, hide_index=True)


def render_heatmap_tab(run_id: Optional[str]):
    """Render parameter heatmap visualizations."""
    st.subheader("Parameter Heatmaps")
    st.caption("Visualize how parameter combinations affect performance")
    
    param_options = {
        'rsi_period': 'RSI Period',
        'rsi_oversold': 'RSI Oversold',
        'rsi_overbought': 'RSI Overbought',
        'bb_period': 'BB Period',
        'bb_std_dev': 'BB Std Dev',
        'stop_loss_pct': 'Stop Loss %',
        'take_profit_pct': 'Take Profit %',
    }
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        param1 = st.selectbox(
            "X-Axis Parameter",
            options=list(param_options.keys()),
            index=1,  # rsi_oversold
            format_func=lambda x: param_options[x],
            key="heatmap_param1"
        )
    
    with col2:
        param2 = st.selectbox(
            "Y-Axis Parameter",
            options=list(param_options.keys()),
            index=5,  # stop_loss_pct
            format_func=lambda x: param_options[x],
            key="heatmap_param2"
        )
    
    with col3:
        metric_labels = {
            'sharpe': 'Sharpe Ratio',
            'return': 'Total Return',
            'win_rate': 'Win Rate',
            'drawdown': 'Max Drawdown'
        }
        metric = st.selectbox(
            "Metric",
            options=list(metric_labels.keys()),
            format_func=lambda x: metric_labels[x],
            key="heatmap_metric"
        )
    
    if param1 == param2:
        st.warning("Please select different parameters for X and Y axes")
        return
    
    # Get heatmap data
    heatmap_df = get_parameter_heatmap_data(param1, param2, metric, run_id)
    
    if heatmap_df.empty:
        st.warning("No data available for selected parameter combination")
        return
    
    # Create pivot table for heatmap
    try:
        pivot_df = heatmap_df.pivot(index=param2, columns=param1, values=metric)
        
        # Create heatmap
        fig = px.imshow(
            pivot_df,
            labels=dict(
                x=param_options[param1],
                y=param_options[param2],
                color=metric.replace('_', ' ').title()
            ),
            title=f"{metric.replace('_', ' ').title()} by {param_options[param1]} and {param_options[param2]}",
            color_continuous_scale='RdYlGn' if metric != 'drawdown' else 'RdYlGn_r',
            aspect='auto'
        )
        
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Best combination from heatmap
        if metric == 'drawdown':
            best_idx = pivot_df.stack().idxmin()
        else:
            best_idx = pivot_df.stack().idxmax()
        
        if isinstance(best_idx, tuple) and len(best_idx) >= 2:
            st.success(f"**Best Combination:** {param_options[param1]}={best_idx[1]}, {param_options[param2]}={best_idx[0]}")
        
    except Exception as e:
        st.error(f"Could not create heatmap: {e}")
        st.dataframe(heatmap_df)


def render_raw_results_tab(
    run_id: Optional[str],
    min_sharpe: Optional[float],
    max_drawdown: Optional[float],
    min_trades: Optional[int],
    min_win_rate: Optional[float]
):
    """Render the raw results table with filtering."""
    st.subheader("All Optimization Results")
    
    # Get filtered results
    results_df = get_optimization_results(
        run_id=run_id,
        min_sharpe=min_sharpe,
        max_drawdown=max_drawdown,
        min_trades=min_trades,
        min_win_rate=min_win_rate,
        limit=500
    )
    
    if results_df.empty:
        st.warning("No results match the current filters")
        return
    
    st.info(f"Showing {len(results_df)} results (filtered)")
    
    # Column selector
    available_columns = [
        'BacktestId', 'TotalReturn', 'SharpeRatio', 'MaxDrawdown', 'WinRate',
        'TotalTrades', 'ProfitFactor', 'rsi_period', 'rsi_oversold', 'rsi_overbought',
        'bb_period', 'bb_std_dev', 'stop_loss_pct', 'take_profit_pct',
        'OptimizationRunId', 'CreatedAt'
    ]
    
    default_columns = [
        'TotalReturn', 'SharpeRatio', 'MaxDrawdown', 'WinRate', 'TotalTrades',
        'rsi_oversold', 'bb_std_dev', 'stop_loss_pct'
    ]
    
    # Filter to existing columns
    available_columns = [c for c in available_columns if c in results_df.columns]
    default_columns = [c for c in default_columns if c in results_df.columns]
    
    selected_columns = st.multiselect(
        "Columns to Display",
        options=available_columns,
        default=default_columns
    )
    
    if not selected_columns:
        selected_columns = default_columns
    
    # Display table
    display_df = results_df[selected_columns].copy()
    
    # Format columns
    if 'TotalReturn' in display_df.columns:
        display_df['TotalReturn'] = display_df['TotalReturn'].apply(
            lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
        )
    if 'MaxDrawdown' in display_df.columns:
        display_df['MaxDrawdown'] = display_df['MaxDrawdown'].apply(
            lambda x: f"{abs(x)*100:.2f}%" if pd.notna(x) else "N/A"
        )
    if 'WinRate' in display_df.columns:
        display_df['WinRate'] = display_df['WinRate'].apply(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
        )
    if 'stop_loss_pct' in display_df.columns:
        display_df['stop_loss_pct'] = display_df['stop_loss_pct'].apply(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
        )
    if 'take_profit_pct' in display_df.columns:
        display_df['take_profit_pct'] = display_df['take_profit_pct'].apply(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
        )
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Export option
    st.divider()
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📥 Export to CSV"):
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"optimization_results_{run_id or 'all'}.csv",
                mime="text/csv"
            )
    
    with col2:
        st.caption("Export all filtered results for external analysis")

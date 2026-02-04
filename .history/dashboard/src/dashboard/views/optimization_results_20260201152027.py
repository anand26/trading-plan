"""
Optimization Results View
=========================
Dashboard view for analyzing parameter optimization results.

Features:
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
    st.title("📊 Parameter Optimization Results")
    st.caption("Analyze and compare parameter combinations from batch backtests")
    
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
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Summary",
        "🎯 Parameter Impact",
        "🗺️ Heatmaps",
        "📋 Raw Results"
    ])
    
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
        st.metric(
            f"Optimal {param_options[selected_param]}",
            f"{best_row['ParamValue']:.2f}" if isinstance(best_row['ParamValue'], float) else best_row['ParamValue']
        )
        st.metric("Avg Sharpe", f"{best_row['AvgSharpe']:.2f}")
        st.metric("Avg Return", f"{best_row['AvgReturn']*100:.2f}%")
        st.metric("Sample Count", f"{best_row['SampleCount']:.0f}")
    
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

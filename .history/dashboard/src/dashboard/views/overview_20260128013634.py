"""
Overview page - Key metrics and equity curve visualization.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from dashboard.database import (
    get_trade_summary,
    get_daily_performance,
    get_equity_curve,
    get_trades,
)
from dashboard.components.charts import create_equity_chart, create_pnl_distribution_chart
from dashboard.components.metrics import render_metric_card, render_metric_row


def render_overview():
    """Render the overview page."""
    st.title("📊 Trading Overview")
    
    # Show current data source indicator
    data_source = st.session_state.get("data_source", "All")
    mode_badges = {
        "All": "🔵 All Data",
        "Backtest": "🟡 Backtest Results",
        "Paper": "🟢 Paper Trading",
        "Live": "🔴 Live Trading"
    }
    st.caption(f"**Data Source:** {mode_badges.get(data_source, data_source)}")
    
    # Check if backtest mode is selected
    if data_source == "Backtest":
        st.warning("⚠️ Individual trade analysis is not available for backtests. Backtests only store summary metrics. Please switch to 'Paper' or 'Live' data source for detailed trade analysis, or use the Backtest Runner tab for backtest metrics.")
        return
    
    # Time period selector
    col1, col2 = st.columns([3, 1])
    with col2:
        time_options = [7, 14, 30, 60, 90, 180, 365, None]
        time_labels = {7: "7 days", 14: "14 days", 30: "30 days", 60: "60 days", 
                      90: "90 days", 180: "180 days", 365: "365 days", None: "All Time"}
        days = st.selectbox(
            "Time Period",
            options=time_options,
            index=7,  # Default to "All Time" for backtests
            format_func=lambda x: time_labels[x]
        )
    
    # ==================== Key Metrics ====================
    st.subheader("Key Performance Metrics")
    
    summary = get_trade_summary(days)
    
    if summary:
        # Calculate derived metrics
        total_trades = summary.get("TotalTrades", 0) or 0
        winning_trades = summary.get("WinningTrades", 0) or 0
        total_pnl = summary.get("TotalPnL", 0) or 0
        avg_win = summary.get("AvgWin", 0) or 0
        avg_loss = abs(summary.get("AvgLoss", 0) or 0)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # Display metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Total P&L",
                value=f"${total_pnl:,.2f}",
                delta=f"{total_trades} trades"
            )
        
        with col2:
            st.metric(
                label="Win Rate",
                value=f"{win_rate:.1f}%",
                delta=f"{winning_trades}W / {total_trades - winning_trades}L"
            )
        
        with col3:
            st.metric(
                label="Profit Factor",
                value=f"{profit_factor:.2f}",
                delta="Avg Win / Avg Loss"
            )
        
        with col4:
            avg_hold_mins = summary.get("AvgHoldingMinutes", 0) or 0
            st.metric(
                label="Avg Hold Time",
                value=f"{avg_hold_mins:.1f} min",
                delta="Per trade"
            )
        
        # Second row of metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Best Trade",
                value=f"${summary.get('MaxWin', 0) or 0:,.2f}",
            )
        
        with col2:
            st.metric(
                label="Worst Trade",
                value=f"${summary.get('MaxLoss', 0) or 0:,.2f}",
            )
        
        with col3:
            st.metric(
                label="Avg Win",
                value=f"${avg_win:,.2f}",
            )
        
        with col4:
            st.metric(
                label="Avg Loss",
                value=f"-${avg_loss:,.2f}",
            )
    else:
        st.warning("No trade data available for the selected period.")
    
    st.divider()
    
    # ==================== Equity Curve ====================
    st.subheader("Equity Curve")
    
    equity_df = get_equity_curve(days)
    
    if not equity_df.empty:
        fig = create_equity_chart(equity_df)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No equity data available. Run some trades to see the equity curve.")
    
    st.divider()
    
    # ==================== Daily P&L ====================
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Daily P&L")
        daily_df = get_daily_performance(days)
        
        if not daily_df.empty:
            fig = create_pnl_distribution_chart(daily_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No daily performance data available.")
    
    with col2:
        st.subheader("P&L by Symbol")
        trades_df = get_trades(days)
        
        if not trades_df.empty:
            symbol_pnl = trades_df.groupby("Symbol")["NetPnL"].agg(["sum", "count", "mean"]).reset_index()
            symbol_pnl.columns = ["Symbol", "Total P&L", "Trades", "Avg P&L"]
            
            fig = px.bar(
                symbol_pnl,
                x="Symbol",
                y="Total P&L",
                color="Total P&L",
                color_continuous_scale=["red", "gray", "green"],
                text="Trades"
            )
            fig.update_layout(
                showlegend=False,
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trade data available.")
    
    st.divider()
    
    # ==================== Recent Trades ====================
    st.subheader("Recent Trades")
    
    trades_df = get_trades(days, limit=20)
    
    if not trades_df.empty:
        # Format the dataframe for display
        display_df = trades_df[[
            "Symbol", "Direction", "EntryTime", "ExitTime", 
            "EntryPrice", "ExitPrice", "Quantity", "NetPnL"
        ]].copy()
        
        display_df["EntryTime"] = pd.to_datetime(display_df["EntryTime"]).dt.strftime("%Y-%m-%d %H:%M")
        display_df["ExitTime"] = pd.to_datetime(display_df["ExitTime"]).dt.strftime("%Y-%m-%d %H:%M")
        display_df["EntryPrice"] = display_df["EntryPrice"].apply(lambda x: f"${x:.2f}" if x is not None else "N/A")
        display_df["ExitPrice"] = display_df["ExitPrice"].apply(lambda x: f"${x:.2f}" if x is not None else "N/A")
        display_df["NetPnL"] = display_df["NetPnL"].apply(
            lambda x: f"🟢 ${x:.2f}" if x >= 0 else f"🔴 ${x:.2f}"
        )
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent trades to display.")


# Auto-execute when run directly by Streamlit multipage navigation
if "data_source" not in st.session_state:
    st.session_state.data_source = "All"

render_overview()

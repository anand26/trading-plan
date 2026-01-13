"""
Trade Analysis page - Detailed trade analysis and patterns.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from ..database import get_trades, get_trade_summary
from ..components.charts import create_trade_scatter, create_hourly_performance_chart


def render_trades():
    """Render the trade analysis page."""
    st.title("📈 Trade Analysis")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        days = st.selectbox(
            "Time Period",
            options=[7, 14, 30, 60, 90, 180, 365],
            index=2,
            format_func=lambda x: f"{x} days"
        )
    
    with col2:
        symbol_filter = st.selectbox(
            "Symbol",
            options=["All", "TQQQ", "SQQQ"],
            index=0
        )
    
    with col3:
        side_filter = st.selectbox(
            "Side",
            options=["All", "Long", "Short"],
            index=0
        )
    
    # Get trades data
    symbol = None if symbol_filter == "All" else symbol_filter
    trades_df = get_trades(days, symbol=symbol, limit=5000)
    
    if side_filter != "All":
        trades_df = trades_df[trades_df["Side"] == side_filter]
    
    if trades_df.empty:
        st.warning("No trades found for the selected filters.")
        return
    
    st.divider()
    
    # ==================== Trade Scatter Plot ====================
    st.subheader("Trade Performance Scatter")
    
    fig = create_trade_scatter(trades_df)
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ==================== Hourly Performance ====================
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Performance by Hour")
        
        trades_df["Hour"] = pd.to_datetime(trades_df["EntryTime"]).dt.hour
        hourly = trades_df.groupby("Hour").agg({
            "PnL": ["sum", "count", "mean"],
            "TradeID": "count"
        }).reset_index()
        hourly.columns = ["Hour", "Total P&L", "Count", "Avg P&L", "Trades"]
        
        fig = px.bar(
            hourly,
            x="Hour",
            y="Total P&L",
            color="Total P&L",
            color_continuous_scale=["red", "gray", "green"],
            text="Trades"
        )
        fig.update_layout(
            xaxis_title="Hour of Day (EST)",
            yaxis_title="Total P&L ($)",
            showlegend=False,
            height=350
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Win Rate by Hour")
        
        hourly_wr = trades_df.groupby("Hour").apply(
            lambda x: (x["PnL"] > 0).sum() / len(x) * 100
        ).reset_index()
        hourly_wr.columns = ["Hour", "Win Rate"]
        
        fig = px.line(
            hourly_wr,
            x="Hour",
            y="Win Rate",
            markers=True
        )
        fig.add_hline(y=50, line_dash="dash", line_color="gray")
        fig.update_layout(
            xaxis_title="Hour of Day (EST)",
            yaxis_title="Win Rate (%)",
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ==================== Trade Duration Analysis ====================
    st.subheader("Trade Duration Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Duration distribution
        trades_df["Duration_Min"] = trades_df["HoldingPeriodSeconds"] / 60
        
        fig = px.histogram(
            trades_df,
            x="Duration_Min",
            nbins=30,
            color_discrete_sequence=["steelblue"]
        )
        fig.update_layout(
            xaxis_title="Trade Duration (minutes)",
            yaxis_title="Number of Trades",
            title="Trade Duration Distribution",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Duration vs P&L
        fig = px.scatter(
            trades_df,
            x="Duration_Min",
            y="PnL",
            color="Symbol",
            hover_data=["Side", "EntryTime"],
            opacity=0.6
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            xaxis_title="Trade Duration (minutes)",
            yaxis_title="P&L ($)",
            title="Duration vs P&L",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ==================== Entry/Exit Reasons ====================
    st.subheader("Entry & Exit Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Entry Reasons**")
        if "EntryReason" in trades_df.columns:
            entry_reasons = trades_df["EntryReason"].value_counts().head(10)
            if not entry_reasons.empty:
                fig = px.pie(
                    values=entry_reasons.values,
                    names=entry_reasons.index,
                    hole=0.4
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No entry reason data available.")
        else:
            st.info("Entry reason data not tracked.")
    
    with col2:
        st.write("**Exit Reasons**")
        if "ExitReason" in trades_df.columns:
            exit_reasons = trades_df["ExitReason"].value_counts().head(10)
            if not exit_reasons.empty:
                fig = px.pie(
                    values=exit_reasons.values,
                    names=exit_reasons.index,
                    hole=0.4
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No exit reason data available.")
        else:
            st.info("Exit reason data not tracked.")
    
    st.divider()
    
    # ==================== Win/Loss Streaks ====================
    st.subheader("Win/Loss Streaks")
    
    trades_df = trades_df.sort_values("EntryTime")
    trades_df["IsWin"] = trades_df["PnL"] > 0
    
    # Calculate streaks
    streaks = []
    current_streak = 0
    current_is_win = None
    
    for _, row in trades_df.iterrows():
        if current_is_win is None:
            current_is_win = row["IsWin"]
            current_streak = 1
        elif row["IsWin"] == current_is_win:
            current_streak += 1
        else:
            streaks.append({"Type": "Win" if current_is_win else "Loss", "Length": current_streak})
            current_is_win = row["IsWin"]
            current_streak = 1
    
    if current_streak > 0:
        streaks.append({"Type": "Win" if current_is_win else "Loss", "Length": current_streak})
    
    if streaks:
        streak_df = pd.DataFrame(streaks)
        
        col1, col2, col3 = st.columns(3)
        
        win_streaks = streak_df[streak_df["Type"] == "Win"]["Length"]
        loss_streaks = streak_df[streak_df["Type"] == "Loss"]["Length"]
        
        with col1:
            st.metric("Max Win Streak", f"{win_streaks.max() if len(win_streaks) > 0 else 0}")
        with col2:
            st.metric("Max Loss Streak", f"{loss_streaks.max() if len(loss_streaks) > 0 else 0}")
        with col3:
            st.metric("Avg Streak Length", f"{streak_df['Length'].mean():.1f}")
    
    st.divider()
    
    # ==================== Full Trade Table ====================
    st.subheader("All Trades")
    
    # Format for display
    display_df = trades_df[[
        "TradeID", "Symbol", "Side", "EntryTime", "ExitTime",
        "EntryPrice", "ExitPrice", "Quantity", "PnL", "PnLPercent",
        "MarketRegime"
    ]].copy()
    
    display_df["EntryTime"] = pd.to_datetime(display_df["EntryTime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df["ExitTime"] = pd.to_datetime(display_df["ExitTime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df["PnLPercent"] = display_df["PnLPercent"].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=400
    )

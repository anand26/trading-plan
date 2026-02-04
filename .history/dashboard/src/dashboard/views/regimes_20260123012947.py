"""
Regime Analysis page - Market regime detection and performance.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dashboard.database import get_market_regimes, get_regime_performance, get_trades


def render_regimes():
    """Render the regime analysis page."""
    st.title("🎯 Market Regime Analysis")
    
    # Filters in a single row
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Show current data source indicator
        data_source = st.session_state.get("data_source", "All")
        mode_badges = {
            "All": "🔵 All Data",
            "Backtest": "🟡 Backtest Results",
            "Paper": "🟢 Paper Trading",
            "Live": "🔴 Live Trading"
        }
        st.caption(f"**Data Source:** {mode_badges.get(data_source, data_source)}")
    
    with col3:
        # Time period selector
        days = st.selectbox(
            "Time Period",
            options=[7, 14, 30, 60, 90, 180],
            index=2,
            format_func=lambda x: f"{x} days",
            label_visibility="collapsed"
        )
    
    # ==================== Regime Performance Summary ====================
    st.subheader("Performance by Market Regime")
    
    regime_perf = get_regime_performance(days)
    
    if not regime_perf.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # P&L by regime
            fig = px.bar(
                regime_perf,
                x="MarketRegime",
                y="TotalPnL",
                color="TotalPnL",
                color_continuous_scale=["red", "gray", "green"],
                text="TradeCount"
            )
            fig.update_layout(
                title="Total P&L by Regime",
                xaxis_title="Market Regime",
                yaxis_title="Total P&L ($)",
                showlegend=False,
                height=350
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Win rate by regime
            fig = px.bar(
                regime_perf,
                x="MarketRegime",
                y="WinRate",
                color="WinRate",
                color_continuous_scale=["red", "yellow", "green"],
                text=regime_perf["WinRate"].apply(lambda x: f"{x:.1f}%" if x is not None else "N/A")
            )
            fig.add_hline(y=50, line_dash="dash", line_color="gray")
            fig.update_layout(
                title="Win Rate by Regime",
                xaxis_title="Market Regime",
                yaxis_title="Win Rate (%)",
                showlegend=False,
                height=350
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)
        
        # Regime summary table
        st.write("**Regime Summary**")
        display_df = regime_perf.copy()
        display_df["TotalPnL"] = display_df["TotalPnL"].apply(lambda x: f"${x:,.2f}" if x is not None else "N/A")
        display_df["AvgPnL"] = display_df["AvgPnL"].apply(lambda x: f"${x:,.2f}" if x is not None else "N/A")
        display_df["WinRate"] = display_df["WinRate"].apply(lambda x: f"{x:.1f}%" if x is not None else "N/A")
        
        st.dataframe(display_df, width='stretch', hide_index=True)
    else:
        st.info("No regime performance data available.")
    
    st.divider()
    
    # ==================== Regime Timeline ====================
    st.subheader("Market Regime Timeline")
    
    regimes_df = get_market_regimes(days)
    
    if not regimes_df.empty:
        # Regime over time
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Market Regime", "RSI", "Momentum")
        )
        
        # Regime classification
        regime_colors = {
            "BULLISH": "green",
            "BEARISH": "red",
            "NEUTRAL": "gray",
            "VOLATILE": "orange",
            "TRENDING_UP": "lightgreen",
            "TRENDING_DOWN": "lightcoral"
        }
        
        for regime in regimes_df["Regime"].unique():
            mask = regimes_df["Regime"] == regime
            fig.add_trace(
                go.Scatter(
                    x=regimes_df[mask]["Timestamp"],
                    y=[regime] * mask.sum(),
                    mode="markers",
                    name=regime,
                    marker=dict(
                        size=10,
                        color=regime_colors.get(regime, "blue")
                    )
                ),
                row=1, col=1
            )
        
        # RSI
        fig.add_trace(
            go.Scatter(
                x=regimes_df["Timestamp"],
                y=regimes_df["RSI"],
                mode="lines",
                name="RSI",
                line=dict(color="purple")
            ),
            row=2, col=1  # type: ignore
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)  # type: ignore
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)  # type: ignore
        
        # Momentum
        fig.add_trace(
            go.Scatter(
                x=regimes_df["Timestamp"],
                y=regimes_df["Momentum"],
                mode="lines",
                name="Momentum",
                line=dict(color="blue")
            ),
            row=3, col=1  # type: ignore
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)  # type: ignore
        
        fig.update_layout(
            height=600,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No market regime data available.")
    
    st.divider()
    
    # ==================== Regime Indicators ====================
    st.subheader("Regime Indicator Analysis")
    
    if not regimes_df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # RSI distribution by regime
            fig = px.box(
                regimes_df,
                x="Regime",
                y="RSI",
                color="Regime"
            )
            fig.update_layout(
                title="RSI Distribution by Regime",
                showlegend=False,
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Volatility distribution by regime
            if "Volatility" in regimes_df.columns:
                fig = px.box(
                    regimes_df,
                    x="Regime",
                    y="Volatility",
                    color="Regime"
                )
                fig.update_layout(
                    title="Volatility Distribution by Regime",
                    showlegend=False,
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Volatility data not available.")
    
    st.divider()
    
    # ==================== Regime Transitions ====================
    st.subheader("Regime Transitions")
    
    if not regimes_df.empty and len(regimes_df) > 1:
        regimes_df = regimes_df.sort_values("Timestamp")
        regimes_df["PrevRegime"] = regimes_df["Regime"].shift(1)
        transitions = regimes_df[regimes_df["Regime"] != regimes_df["PrevRegime"]].dropna()
        
        if not transitions.empty:
            # Transition matrix
            transition_matrix = pd.crosstab(
                transitions["PrevRegime"],
                transitions["Regime"],
                normalize="index"
            ) * 100
            
            fig = px.imshow(
                transition_matrix,
                labels=dict(x="To Regime", y="From Regime", color="Probability (%)"),
                color_continuous_scale="Blues",
                text_auto=".1f"  # type: ignore
            )
            fig.update_layout(
                title="Regime Transition Probabilities (%)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Recent transitions
            st.write("**Recent Regime Changes**")
            recent_transitions = transitions.tail(10)[[
                "Timestamp", "PrevRegime", "Regime", "Confidence", "RSI", "Momentum"
            ]].copy()
            recent_transitions["Timestamp"] = pd.to_datetime(recent_transitions["Timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
            recent_transitions.columns = ["Time", "From", "To", "Confidence", "RSI", "Momentum"]
            st.dataframe(recent_transitions, use_container_width=True, hide_index=True)
        else:
            st.info("No regime transitions detected in the selected period.")
    else:
        st.info("Insufficient data for transition analysis.")
    
    st.divider()
    
    # ==================== Optimal Trading Hours by Regime ====================
    st.subheader("Optimal Trading Hours by Regime")
    
    trades_df = get_trades(days)
    
    if not trades_df.empty and "MarketRegime" in trades_df.columns:
        trades_df["Hour"] = pd.to_datetime(trades_df["EntryTime"]).dt.hour
        
        hourly_regime = trades_df.groupby(["MarketRegime", "Hour"]).agg({
            "NetPnL": ["sum", "mean", "count"]
        }).reset_index()
        hourly_regime.columns = ["MarketRegime", "Hour", "TotalPnL", "AvgPnL", "Trades"]
        
        fig = px.line(
            hourly_regime,
            x="Hour",
            y="AvgPnL",
            color="MarketRegime",
            markers=True
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            title="Average P&L by Hour and Regime",
            xaxis_title="Hour of Day (EST)",
            yaxis_title="Average P&L ($)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trade data with regime information available.")


# Auto-execute when run directly by Streamlit multipage navigation
if "data_source" not in st.session_state:
    st.session_state.data_source = "All"

render_regimes()

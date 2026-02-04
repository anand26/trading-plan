"""
Plotly chart components for the trading dashboard.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_equity_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create an equity curve chart with portfolio value over time.
    
    Args:
        df: DataFrame with columns [Date, PortfolioValue, CumulativePnL]
    
    Returns:
        Plotly Figure object
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("Portfolio Value", "Cumulative P&L")
    )
    
    # Portfolio value
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["PortfolioValue"],
            mode="lines",
            name="Portfolio Value",
            line=dict(color="steelblue", width=2),
            fill="tozeroy",
            fillcolor="rgba(70, 130, 180, 0.2)"
        ),
        row=1, col=1
    )
    
    # Cumulative P&L
    if "CumulativePnL" in df.columns:
        # Handle None values - fill with 0 for color comparison
        pnl_values = df["CumulativePnL"].fillna(0)
        colors = ["green" if (x is not None and x >= 0) else "red" for x in pnl_values]
        fig.add_trace(
            go.Bar(
                x=df["Date"],
                y=pnl_values,
                name="Cumulative P&L",
                marker_color=colors
            ),
            row=2, col=1
        )
    
    fig.update_layout(
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified"
    )
    
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Value ($)", row=1, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=2, col=1)
    
    return fig


def create_pnl_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create a daily P&L distribution bar chart.
    
    Args:
        df: DataFrame with columns [Date, DailyPnL]
    
    Returns:
        Plotly Figure object
    """
    colors = ["green" if x >= 0 else "red" for x in df["DailyPnL"]]
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Bar(
            x=df["Date"],
            y=df["DailyPnL"],
            marker_color=colors,
            name="Daily P&L"
        )
    )
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    
    # Add 7-day moving average
    if len(df) >= 7:
        df["MA7"] = df["DailyPnL"].rolling(window=7).mean()
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df["MA7"],
                mode="lines",
                name="7-Day MA",
                line=dict(color="orange", width=2)
            )
        )
    
    fig.update_layout(
        title="Daily P&L Distribution",
        xaxis_title="Date",
        yaxis_title="P&L ($)",
        height=300,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig


def create_trade_scatter(df: pd.DataFrame) -> go.Figure:
    """
    Create a scatter plot of individual trades.
    
    Args:
        df: DataFrame with columns [EntryTime, NetPnL, Symbol, Direction, Quantity]
    
    Returns:
        Plotly Figure object
    """
    # Add color based on P&L
    df = df.copy()
    df["Color"] = df["NetPnL"].apply(lambda x: "green" if x >= 0 else "red")
    df["Size"] = abs(df["NetPnL"]).clip(lower=1)
    
    fig = px.scatter(
        df,
        x="EntryTime",
        y="NetPnL",
        color="Symbol",
        size="Size",
        hover_data=["Direction", "Quantity", "EntryPrice", "ExitPrice"],
        opacity=0.7
    )
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    
    fig.update_layout(
        title="Trade Performance Over Time",
        xaxis_title="Entry Time",
        yaxis_title="P&L ($)",
        height=400,
        showlegend=True
    )
    
    return fig


def create_hourly_performance_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create a chart showing performance by hour of day.
    
    Args:
        df: DataFrame with columns [Hour, TotalPnL, WinRate, TradeCount]
    
    Returns:
        Plotly Figure object
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=("Total P&L by Hour", "Win Rate by Hour")
    )
    
    colors = ["green" if x >= 0 else "red" for x in df["TotalPnL"]]
    
    # P&L by hour
    fig.add_trace(
        go.Bar(
            x=df["Hour"],
            y=df["TotalPnL"],
            marker_color=colors,
            name="Total P&L",
            text=df["TradeCount"],
            textposition="outside"
        ),
        row=1, col=1
    )
    
    # Win rate by hour
    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["WinRate"],
            mode="lines+markers",
            name="Win Rate",
            line=dict(color="blue", width=2),
            marker=dict(size=8)
        ),
        row=2, col=1
    )
    
    fig.add_hline(y=50, line_dash="dash", line_color="gray", row=2, col=1)  # type: ignore
    
    fig.update_layout(
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    fig.update_xaxes(title_text="Hour of Day (EST)", row=2, col=1)
    fig.update_yaxes(title_text="P&L ($)", row=1, col=1)
    fig.update_yaxes(title_text="Win Rate (%)", row=2, col=1)
    
    return fig


def create_drawdown_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create a drawdown visualization chart.
    
    Args:
        df: DataFrame with columns [Date, PortfolioValue, PeakValue, DrawdownPercent]
    
    Returns:
        Plotly Figure object
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.6, 0.4],
        subplot_titles=("Portfolio Value vs Peak", "Drawdown %")
    )
    
    # Portfolio value and peak
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["PortfolioValue"],
            mode="lines",
            name="Portfolio Value",
            line=dict(color="steelblue", width=2)
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["PeakValue"],
            mode="lines",
            name="Peak Value",
            line=dict(color="green", width=1, dash="dash")
        ),
        row=1, col=1
    )
    
    # Drawdown percentage
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["DrawdownPercent"],
            mode="lines",
            name="Drawdown %",
            line=dict(color="red", width=2),
            fill="tozeroy",
            fillcolor="rgba(255, 0, 0, 0.2)"
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Value ($)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    
    return fig


def create_regime_timeline_chart(df: pd.DataFrame) -> go.Figure:
    """
    Create a market regime timeline visualization.
    
    Args:
        df: DataFrame with columns [Timestamp, Regime, RSI, Momentum]
    
    Returns:
        Plotly Figure object
    """
    regime_colors = {
        "BULLISH": "green",
        "BEARISH": "red",
        "NEUTRAL": "gray",
        "VOLATILE": "orange",
        "TRENDING_UP": "lightgreen",
        "TRENDING_DOWN": "lightcoral"
    }
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.4, 0.3, 0.3],
        subplot_titles=("Market Regime", "RSI", "Momentum")
    )
    
    # Regime scatter
    for regime in df["Regime"].unique():
        mask = df["Regime"] == regime
        fig.add_trace(
            go.Scatter(
                x=df[mask]["Timestamp"],
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
            x=df["Timestamp"],
            y=df["RSI"],
            mode="lines",
            name="RSI",
            line=dict(color="purple", width=2)
        ),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)  # type: ignore
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)  # type: ignore
    
    # Momentum
    fig.add_trace(
        go.Scatter(
            x=df["Timestamp"],
            y=df["Momentum"],
            mode="lines",
            name="Momentum",
            line=dict(color="blue", width=2)
        ),
        row=3, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)  # type: ignore
    
    fig.update_layout(
        height=600,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    
    return fig

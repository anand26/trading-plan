"""
Table display components for the trading dashboard.
"""

import streamlit as st
import pandas as pd
from typing import Optional


def render_trade_table(
    df: pd.DataFrame,
    height: int = 400,
    show_index: bool = False
):
    """
    Render a formatted trade table.
    
    Args:
        df: DataFrame with trade data
        height: Table height in pixels
        show_index: Whether to show row index
    """
    if df.empty:
        st.info("No trade data to display.")
        return
    
    # Format the dataframe
    display_df = df.copy()
    
    # Format datetime columns
    datetime_cols = ["EntryTime", "ExitTime"]
    for col in datetime_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_datetime(display_df[col]).dt.strftime("%Y-%m-%d %H:%M")
    
    # Format price columns
    price_cols = ["EntryPrice", "ExitPrice"]
    for col in price_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}")
    
    # Format P&L with color indicator
    if "NetPnL" in display_df.columns:
        display_df["NetPnL"] = display_df["NetPnL"].apply(
            lambda x: f"🟢 ${x:.2f}" if x >= 0 else f"🔴 ${x:.2f}"
        )
    elif "PnL" in display_df.columns:
        display_df["PnL"] = display_df["PnL"].apply(
            lambda x: f"🟢 ${x:.2f}" if x >= 0 else f"🔴 ${x:.2f}"
        )
    
    # Format percentage columns
    pct_cols = ["PnLPercent", "WinRate"]
    for col in pct_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=not show_index,
        height=height
    )


def render_parameter_table(
    df: pd.DataFrame,
    editable: bool = False
):
    """
    Render a parameter configuration table.
    
    Args:
        df: DataFrame with parameter data (ParameterName, ParameterValue, etc.)
        editable: Whether the table should be editable
    """
    if df.empty:
        st.info("No parameters to display.")
        return
    
    if editable:
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ParameterName": st.column_config.TextColumn(
                    "Parameter",
                    disabled=True
                ),
                "ParameterValue": st.column_config.TextColumn(
                    "Value",
                    disabled=False
                ),
                "DataType": st.column_config.TextColumn(
                    "Type",
                    disabled=True
                ),
                "Description": st.column_config.TextColumn(
                    "Description",
                    disabled=True
                )
            }
        )
        return edited_df
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_backtest_table(df: pd.DataFrame):
    """
    Render a backtest results table with status indicators.
    
    Args:
        df: DataFrame with backtest data
    """
    if df.empty:
        st.info("No backtest results to display.")
        return
    
    display_df = df.copy()
    
    # Format datetime columns
    if "StartTime" in display_df.columns:
        display_df["StartTime"] = pd.to_datetime(display_df["StartTime"]).dt.strftime("%Y-%m-%d %H:%M")
    if "EndTime" in display_df.columns:
        display_df["EndTime"] = pd.to_datetime(display_df["EndTime"]).dt.strftime("%Y-%m-%d %H:%M")
    
    # Add status icons
    status_icons = {
        "Completed": "✅",
        "Failed": "❌",
        "Running": "🔄",
        "Pending": "⏳"
    }
    if "Status" in display_df.columns:
        display_df["Status"] = display_df["Status"].apply(
            lambda x: f"{status_icons.get(x, '❓')} {x}"
        )
    
    # Format currency columns
    if "InitialCapital" in display_df.columns:
        display_df["InitialCapital"] = display_df["InitialCapital"].apply(lambda x: f"${x:,.0f}")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_learning_table(df: pd.DataFrame):
    """
    Render a learning history table.
    
    Args:
        df: DataFrame with learning data
    """
    if df.empty:
        st.info("No learning history to display.")
        return
    
    display_df = df.copy()
    
    # Format timestamp
    if "Timestamp" in display_df.columns:
        display_df["Timestamp"] = pd.to_datetime(display_df["Timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
    
    # Format confidence score
    if "ConfidenceScore" in display_df.columns:
        display_df["ConfidenceScore"] = display_df["ConfidenceScore"].apply(lambda x: f"{x:.1%}")
    
    # Add type icons
    type_icons = {
        "PARAMETER_OPTIMIZATION": "⚙️",
        "REGIME_DETECTION": "🎯",
        "TRADE_PATTERN": "📊",
        "CORRECTION": "🔧",
        "BACKTEST_INSIGHT": "📈"
    }
    if "LearningType" in display_df.columns:
        display_df["LearningType"] = display_df["LearningType"].apply(
            lambda x: f"{type_icons.get(x, '📝')} {x}"
        )
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_regime_table(df: pd.DataFrame):
    """
    Render a regime performance table.
    
    Args:
        df: DataFrame with regime performance data
    """
    if df.empty:
        st.info("No regime data to display.")
        return
    
    display_df = df.copy()
    
    # Format P&L columns
    pnl_cols = ["TotalPnL", "AvgPnL"]
    for col in pnl_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"${x:,.2f}")
    
    # Format win rate
    if "WinRate" in display_df.columns:
        display_df["WinRate"] = display_df["WinRate"].apply(lambda x: f"{x:.1f}%")
    
    # Add regime icons
    regime_icons = {
        "BULLISH": "🟢",
        "BEARISH": "🔴",
        "NEUTRAL": "⚪",
        "VOLATILE": "🟠",
        "TRENDING_UP": "📈",
        "TRENDING_DOWN": "📉"
    }
    if "MarketRegime" in display_df.columns:
        display_df["MarketRegime"] = display_df["MarketRegime"].apply(
            lambda x: f"{regime_icons.get(x, '❓')} {x}"
        )
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_audit_log_table(df: pd.DataFrame):
    """
    Render an audit log table with status indicators.
    
    Args:
        df: DataFrame with audit log data
    """
    if df.empty:
        st.info("No audit log entries to display.")
        return
    
    display_df = df.copy()
    
    # Format timestamp
    if "Timestamp" in display_df.columns:
        display_df["Timestamp"] = pd.to_datetime(display_df["Timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Add status icons
    if "Success" in display_df.columns:
        display_df["Status"] = display_df["Success"].apply(lambda x: "✅" if x else "❌")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)

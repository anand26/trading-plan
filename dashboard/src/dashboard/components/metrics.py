"""
Metric display components for the trading dashboard.
"""

import streamlit as st
from typing import Optional, Union


def render_metric_card(
    label: str,
    value: Union[str, float, int],
    delta: Optional[Union[str, float]] = None,
    delta_color: str = "normal",
    help_text: Optional[str] = None
):
    """
    Render a styled metric card.
    
    Args:
        label: The metric label
        value: The metric value
        delta: Optional delta/change value
        delta_color: Color for delta ("normal", "inverse", "off")
        help_text: Optional help tooltip text
    """
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text
    )


def render_metric_row(metrics: list[dict]):
    """
    Render a row of metrics.
    
    Args:
        metrics: List of metric dictionaries with keys:
            - label: str
            - value: str/float/int
            - delta: Optional[str/float]
            - delta_color: Optional[str]
            - help: Optional[str]
    """
    cols = st.columns(len(metrics))
    
    for col, metric in zip(cols, metrics):
        with col:
            render_metric_card(
                label=metric["label"],
                value=metric["value"],
                delta=metric.get("delta"),
                delta_color=metric.get("delta_color", "normal"),
                help_text=metric.get("help")
            )


def render_kpi_summary(
    total_pnl: float,
    win_rate: float,
    profit_factor: float,
    sharpe_ratio: float,
    max_drawdown: float,
    total_trades: int
):
    """
    Render a comprehensive KPI summary section.
    
    Args:
        total_pnl: Total profit/loss in dollars
        win_rate: Win rate as percentage (0-100)
        profit_factor: Profit factor ratio
        sharpe_ratio: Sharpe ratio
        max_drawdown: Maximum drawdown as percentage
        total_trades: Total number of trades
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pnl_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric(
            label="💰 Total P&L",
            value=f"${total_pnl:,.2f}",
            delta=f"{total_trades} trades",
            delta_color="off"
        )
        
        st.metric(
            label="📊 Profit Factor",
            value=f"{profit_factor:.2f}",
            delta="Good" if profit_factor >= 1.5 else "Needs Work",
            delta_color="normal" if profit_factor >= 1.5 else "inverse"
        )
    
    with col2:
        st.metric(
            label="🎯 Win Rate",
            value=f"{win_rate:.1f}%",
            delta="Above 50%" if win_rate >= 50 else "Below 50%",
            delta_color="normal" if win_rate >= 50 else "inverse"
        )
        
        st.metric(
            label="📉 Max Drawdown",
            value=f"{max_drawdown:.1f}%",
            delta="Risk Level",
            delta_color="inverse" if abs(max_drawdown) > 20 else "off"
        )
    
    with col3:
        st.metric(
            label="📈 Sharpe Ratio",
            value=f"{sharpe_ratio:.2f}",
            delta="Good" if sharpe_ratio >= 1.0 else "Low",
            delta_color="normal" if sharpe_ratio >= 1.0 else "inverse"
        )
        
        st.metric(
            label="🔢 Total Trades",
            value=f"{total_trades:,}",
            delta_color="off"
        )


def render_performance_indicator(
    value: float,
    threshold_good: float,
    threshold_bad: float,
    label: str,
    format_str: str = "{:.2f}",
    inverse: bool = False
):
    """
    Render a performance indicator with color coding.
    
    Args:
        value: The metric value
        threshold_good: Value above which performance is good
        threshold_bad: Value below which performance is bad
        label: Display label
        format_str: Format string for the value
        inverse: If True, lower is better
    """
    if inverse:
        if value <= threshold_good:
            color = "🟢"
            status = "Good"
        elif value >= threshold_bad:
            color = "🔴"
            status = "Poor"
        else:
            color = "🟡"
            status = "OK"
    else:
        if value >= threshold_good:
            color = "🟢"
            status = "Good"
        elif value <= threshold_bad:
            color = "🔴"
            status = "Poor"
        else:
            color = "🟡"
            status = "OK"
    
    st.markdown(f"{color} **{label}**: {format_str.format(value)} ({status})")


def render_alert_box(
    message: str,
    alert_type: str = "info"
):
    """
    Render an alert box.
    
    Args:
        message: The alert message
        alert_type: One of "info", "success", "warning", "error"
    """
    if alert_type == "info":
        st.info(message)
    elif alert_type == "success":
        st.success(message)
    elif alert_type == "warning":
        st.warning(message)
    elif alert_type == "error":
        st.error(message)
    else:
        st.info(message)

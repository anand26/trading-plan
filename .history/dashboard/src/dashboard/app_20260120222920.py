"""
TQQQ/SQQQ Trading Dashboard - Main Application

A Streamlit-based performance visualization dashboard for the adaptive trading system.

Run with:
    streamlit run src/dashboard/app.py
"""

import streamlit as st
from datetime import datetime

from dashboard.config import dashboard_config
from dashboard.views import (
    render_overview,
    render_trades,
    render_regimes,
    render_learning,
    render_status,
    render_backtest_runner,
)


def configure_page():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title=dashboard_config.title,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": "https://github.com/your-repo/trading-system",
            "Report a bug": "https://github.com/your-repo/trading-system/issues",
            "About": "TQQQ/SQQQ Adaptive Trading System Dashboard"
        }
    )


def render_sidebar():
    """Render the sidebar navigation."""
    with st.sidebar:
        st.title("📊 Trading Dashboard")
        st.caption(f"v0.1.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        st.divider()
        
        # Data Source Mode Selector
        st.subheader("📁 Data Source")
        data_source = st.selectbox(
            "Select Data Source",
            options=["Backtest", "Paper", "Live", "All"],
            index=0,
            help="Filter dashboard to show Backtest, Paper Trading, Live, or All data",
            label_visibility="collapsed"
        )
        st.session_state["data_source"] = data_source
        
        # Show indicator for current mode
        mode_colors = {
            "All": "🔵",
            "Backtest": "🟡",
            "Paper": "🟢",
            "Live": "🔴"
        }
        st.caption(f"{mode_colors.get(data_source, '')} Viewing: **{data_source}** data")
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigation",
            options=[
                "🚀 Backtest Runner",
                "📊 Overview",
                "📈 Trade Analysis",
                "🎯 Regime Analysis",
                "🧠 Learning Insights",
                "⚙️ System Status"
            ],
            index=0,  # Default to Backtest Runner
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Quick stats
        st.subheader("Quick Stats")
        
        # These would be populated from the database
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Today's P&L", "$---", "---")
        with col2:
            st.metric("Open Positions", "---", "---")
        
        st.divider()
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox(
            "Auto-refresh",
            value=False,
            help=f"Refresh every {dashboard_config.refresh_interval} seconds"
        )
        
        if auto_refresh:
            st.info(f"Refreshing every {dashboard_config.refresh_interval}s")
            # Note: Streamlit doesn't have built-in auto-refresh
            # You'd need to use st.rerun() with a timer in production
        
        st.divider()
        
        # Footer
        st.caption("Built with Streamlit & Plotly")
        st.caption("© 2026 Trading System")
        
        return page


def main():
    """Main application entry point."""
    # Configure page
    configure_page()
    
    # Initialize session state for data source if not present
    if "data_source" not in st.session_state:
        st.session_state["data_source"] = "All"
    
    # Custom CSS
    st.markdown("""
        <style>
        .stMetric {
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 5px;
        }
        .stMetric:hover {
            background-color: #e0e2e6;
        }
        div[data-testid="stMetricValue"] {
            font-size: 24px;
        }
        .streamlit-expanderHeader {
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Route to appropriate page
    if page == "� Backtest Runner":
        render_backtest_runner()
    elif page == "📊 Overview":
        render_overview()
    elif page == "📈 Trade Analysis":
        render_trades()
    elif page == "🎯 Regime Analysis":
        render_regimes()
    elif page == "🧠 Learning Insights":
        render_learning()
    elif page == "⚙️ System Status":
        render_status()
    else:
        render_backtest_runner()


if __name__ == "__main__":
    main()

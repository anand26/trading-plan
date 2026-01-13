"""
TQQQ/SQQQ Trading Dashboard - Main Application

A Streamlit-based performance visualization dashboard for the adaptive trading system.

Run with:
    streamlit run src/dashboard/app.py
"""

import streamlit as st
from datetime import datetime

from .config import dashboard_config
from .pages import (
    render_overview,
    render_trades,
    render_regimes,
    render_learning,
    render_status,
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
        
        # Navigation
        page = st.radio(
            "Navigation",
            options=[
                "📊 Overview",
                "📈 Trade Analysis",
                "🎯 Regime Analysis",
                "🧠 Learning Insights",
                "⚙️ System Status"
            ],
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
    if page == "📊 Overview":
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
        render_overview()


if __name__ == "__main__":
    main()

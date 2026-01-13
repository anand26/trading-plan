"""
System Status page - Health monitoring and system status.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from ..database import (
    check_database_health,
    get_backtest_runs,
    get_audit_log,
    get_current_parameters,
)


def render_status():
    """Render the system status page."""
    st.title("⚙️ System Status")
    
    # ==================== Health Check ====================
    st.subheader("System Health")
    
    health = check_database_health()
    
    # Overall status
    if health["connected"]:
        st.success("🟢 Database Connected")
    else:
        st.error("🔴 Database Disconnected")
        st.warning("Please check your database connection settings.")
        return
    
    # Component status
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Database Tables**")
        for table, count in health.get("tables", {}).items():
            if count >= 0:
                st.write(f"✅ {table}: {count:,} rows")
            else:
                st.write(f"❌ {table}: Error")
    
    with col2:
        st.write("**Last Activity**")
        last_trade = health.get("last_trade")
        if last_trade:
            st.write(f"📊 Last Trade: {last_trade}")
            
            # Check if recent
            if isinstance(last_trade, datetime):
                age = datetime.now() - last_trade
                if age < timedelta(hours=1):
                    st.success("Trading activity is recent")
                elif age < timedelta(days=1):
                    st.warning(f"No trades in {age.total_seconds() / 3600:.1f} hours")
                else:
                    st.error(f"No trades in {age.days} days")
        else:
            st.info("No trade history")
        
        last_regime = health.get("last_regime")
        if last_regime:
            st.write(f"🎯 Last Regime: {last_regime}")
        else:
            st.info("No regime data")
    
    with col3:
        st.write("**Integration Status**")
        
        # Check for MCP servers (would need actual health endpoints)
        st.write("🔧 LEAN-Ops MCP: Check manually")
        st.write("🧠 Trade-Mind MCP: Check manually")
        st.write("📈 Alpaca API: Check manually")
    
    st.divider()
    
    # ==================== Recent Backtests ====================
    st.subheader("Recent Backtest Runs")
    
    backtests = get_backtest_runs(20)
    
    if not backtests.empty:
        # Status summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            completed = (backtests["Status"] == "Completed").sum()
            st.metric("Completed", completed)
        
        with col2:
            failed = (backtests["Status"] == "Failed").sum()
            st.metric("Failed", failed)
        
        with col3:
            running = (backtests["Status"] == "Running").sum()
            st.metric("Running", running)
        
        # Backtest table
        display_df = backtests.copy()
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
        display_df["Status"] = display_df["Status"].apply(
            lambda x: f"{status_icons.get(x, '❓')} {x}"
        )
        
        st.dataframe(
            display_df[[
                "RunID", "AlgorithmName", "Status", 
                "StartTime", "BacktestStartDate", "BacktestEndDate", "InitialCapital"
            ]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No backtest runs recorded yet.")
    
    st.divider()
    
    # ==================== Audit Log ====================
    st.subheader("Recent Operations")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        audit_days = st.selectbox(
            "Time Period",
            options=[1, 3, 7, 14, 30],
            index=2,
            format_func=lambda x: f"{x} days"
        )
    
    audit_log = get_audit_log(audit_days)
    
    if not audit_log.empty:
        # Filter by success/failure
        filter_type = st.radio(
            "Filter",
            options=["All", "Success", "Failed"],
            horizontal=True
        )
        
        if filter_type == "Success":
            audit_log = audit_log[audit_log["Success"] == True]
        elif filter_type == "Failed":
            audit_log = audit_log[audit_log["Success"] == False]
        
        # Display log
        display_df = audit_log.copy()
        display_df["Timestamp"] = pd.to_datetime(display_df["Timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        display_df["Status"] = display_df["Success"].apply(lambda x: "✅" if x else "❌")
        
        st.dataframe(
            display_df[[
                "Timestamp", "Status", "Operation", "Details", "ErrorMessage"
            ]].head(50),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No audit log entries for the selected period.")
    
    st.divider()
    
    # ==================== Quick Actions ====================
    st.subheader("Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Database**")
        if st.button("🔄 Refresh Connection"):
            st.cache_resource.clear()
            st.rerun()
        
        if st.button("📊 View Full Schema"):
            st.info("Connect to SQL Server Management Studio to view full schema.")
    
    with col2:
        st.write("**MCP Servers**")
        st.markdown("""
        To manage MCP servers, use Claude Desktop or VS Code Copilot:
        
        - `run_backtest` - Start a backtest
        - `deploy_paper` - Deploy to paper trading
        - `suggest_corrections` - Get parameter suggestions
        """)
    
    with col3:
        st.write("**Documentation**")
        st.markdown("""
        - [LEAN Documentation](https://www.quantconnect.com/docs/)
        - [Alpaca API Docs](https://docs.alpaca.markets/)
        - Project README files
        """)
    
    st.divider()
    
    # ==================== Configuration Summary ====================
    st.subheader("Configuration Summary")
    
    with st.expander("📁 Current Parameters", expanded=False):
        params = get_current_parameters()
        if not params.empty:
            st.dataframe(params, use_container_width=True, hide_index=True)
        else:
            st.info("No parameters configured.")
    
    with st.expander("🔧 Environment Info", expanded=False):
        st.write("**Connection String (masked):**")
        from ..config import db_config
        masked_conn = db_config.connection_string.replace(
            db_config.password or "", "****"
        ) if db_config.password else db_config.connection_string
        st.code(masked_conn)
        
        st.write("**Dashboard Settings:**")
        from ..config import dashboard_config
        st.json({
            "title": dashboard_config.title,
            "refresh_interval": dashboard_config.refresh_interval,
            "debug": dashboard_config.debug
        })

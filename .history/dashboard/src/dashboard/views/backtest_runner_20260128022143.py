"""
Backtest Runner page - Run backtests and monitor webhooks from the UI.
"""

import streamlit as st
import pandas as pd
import sys
from datetime import datetime, timedelta
from pathlib import Path
import json
import uuid
import subprocess
import threading
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, asdict

# Handle imports for both direct execution and module import
try:
    from dashboard.database import (
        get_db_connection,
        get_webhook_events,
        get_backtest_sessions,
        create_backtest_session,
        update_backtest_session_status,
    )
except ImportError:
    # Fallback for when dashboard package is not in path
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from database import (
            get_db_connection,
            get_webhook_events,
            get_backtest_sessions,
            create_backtest_session,
            update_backtest_session_status,
        )
    except ImportError:
        # Define stubs for functions that may not exist yet
        def get_db_connection():
            return None
        def get_webhook_events(session_id, limit=100):
            return pd.DataFrame()
        def get_backtest_sessions(limit=20):
            return pd.DataFrame()
        def create_backtest_session(*args, **kwargs):
            return False
        def update_backtest_session_status(*args, **kwargs):
            return False


# ==================== Default Settings ====================
# NOTE: RSI thresholds relaxed (45/55) for testing with limited data
# For production with more historical data, use 30/70

DEFAULT_STRATEGY_PARAMS = {
    "rsi_period": 14,
    "rsi_oversold": 45.0,  # Relaxed for testing (normally 30)
    "rsi_overbought": 55.0,  # Relaxed for testing (normally 70)
    "bb_period": 20,
    "bb_std_dev": 2.0,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.025,
    "position_size_pct": 0.5,
    "max_pyramid_levels": 3,
    "webhook_interval_minutes": 5,
}

DEFAULT_BACKTEST_CONFIG = {
    "start_date": "2026-01-02",
    "end_date": "2026-01-13",
    "initial_cash": 100000.0,
    "algorithm_name": "TQQQScalpingAlgorithm",
}


def get_project_paths() -> Dict[str, Path]:
    """Get project paths relative to dashboard."""
    dashboard_src = Path(__file__).parent.parent
    project_root = dashboard_src.parent.parent.parent
    
    return {
        "project_root": project_root,
        "backtest": project_root / "backtest",
        "results": project_root / "backtest" / "results",
        "algorithms": project_root / "algorithms",
        "lean": project_root / "quantconnect-lean",
        "config": project_root / "backtest" / "tqqq_backtest_config.json",
    }


def load_saved_params() -> Dict[str, Any]:
    """Load previously saved parameters from config or use defaults."""
    paths = get_project_paths()
    config_path = paths["config"]
    
    params = DEFAULT_STRATEGY_PARAMS.copy()
    backtest_config = DEFAULT_BACKTEST_CONFIG.copy()
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                saved = json.load(f)
                # Extract parameters section
                if "parameters" in saved:
                    p = saved["parameters"]
                    if "rsi-period" in p:
                        params["rsi_period"] = int(p.get("rsi-period", 14))
                    if "rsi-oversold" in p:
                        params["rsi_oversold"] = float(p.get("rsi-oversold", 30.0))
                    if "rsi-overbought" in p:
                        params["rsi_overbought"] = float(p.get("rsi-overbought", 70.0))
                    if "bb-period" in p:
                        params["bb_period"] = int(p.get("bb-period", 20))
                    if "bb-std-dev" in p:
                        params["bb_std_dev"] = float(p.get("bb-std-dev", 2.0))
                    if "stop-loss-pct" in p:
                        params["stop_loss_pct"] = float(p.get("stop-loss-pct", 0.02))
                    if "start-date" in p:
                        backtest_config["start_date"] = p.get("start-date", "2024-01-01")
                    if "end-date" in p:
                        backtest_config["end_date"] = p.get("end-date", "2024-12-31")
                    if "cash" in p:
                        backtest_config["initial_cash"] = float(p.get("cash", 100000))
        except Exception as e:
            st.warning(f"Could not load saved config: {e}")
    
    return {**params, **backtest_config}


def save_params_to_config(params: Dict[str, Any]) -> bool:
    """Save updated parameters to config file."""
    paths = get_project_paths()
    config_path = paths["config"]
    
    # Load existing config or create new
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Update parameters section
    if "parameters" not in config:
        config["parameters"] = {}
    
    config["parameters"]["start-date"] = params.get("start_date", "2024-01-01")
    config["parameters"]["end-date"] = params.get("end_date", "2024-12-31")
    config["parameters"]["cash"] = str(params.get("initial_cash", 100000))
    config["parameters"]["rsi-period"] = str(params.get("rsi_period", 14))
    config["parameters"]["rsi-oversold"] = str(params.get("rsi_oversold", 30.0))
    config["parameters"]["rsi-overbought"] = str(params.get("rsi_overbought", 70.0))
    config["parameters"]["bb-period"] = str(params.get("bb_period", 20))
    config["parameters"]["bb-std-dev"] = str(params.get("bb_std_dev", 2.0))
    config["parameters"]["stop-loss-pct"] = str(params.get("stop_loss_pct", 0.02))
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save config: {e}")
        return False


# ==================== Backtest Execution ====================

def generate_session_id() -> str:
    """Generate unique session ID for backtest."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"BT_{timestamp}_{short_uuid}"


def get_backtest_runs_from_db(limit: int = 20) -> pd.DataFrame:
    """Get recent backtest runs from database."""
    # Use the imported function from database.py
    return get_backtest_sessions(limit)


def get_webhook_events_from_file(session_id: str) -> pd.DataFrame:
    """Get webhook events for a session from the log file."""
    paths = get_project_paths()
    webhook_log = paths["results"] / session_id / "webhook_log.txt"
    
    events = []
    
    if webhook_log.exists():
        try:
            with open(webhook_log, 'r') as f:
                for line in f:
                    # Parse webhook log line
                    if "[WEBHOOK" in line:
                        # Parse the webhook log format
                        parts = line.split("|")
                        webhook_type = "UNKNOWN"
                        symbol = ""
                        price = 0.0
                        reason = ""
                        
                        if len(parts) >= 3:
                            # Extract type from first part
                            if "SIGNAL" in parts[0]:
                                webhook_type = "SIGNAL"
                            elif "SCHEDULED" in parts[0]:
                                webhook_type = "SCHEDULED"
                            elif "ALERT" in parts[0]:
                                webhook_type = "ALERT"
                            elif "STATUS" in parts[0]:
                                webhook_type = "STATUS"
                            
                            # Extract symbol and price from second part
                            if "@" in parts[1]:
                                symbol_price = parts[1].strip().split("@")
                                symbol = symbol_price[0].strip()
                                try:
                                    price = float(symbol_price[1].strip())
                                except (ValueError, IndexError):
                                    pass
                            
                            # Reason from third part
                            reason = parts[2].strip() if len(parts) > 2 else ""
                        
                        events.append({
                            "timestamp": line[:23] if len(line) > 23 else "",
                            "type": webhook_type,
                            "symbol": symbol,
                            "price": price,
                            "reason": reason,
                            "raw": line.strip()
                        })
        except Exception as e:
            st.warning(f"Could not read webhook log: {e}")
    
    return pd.DataFrame(events) if events else pd.DataFrame()


def get_all_webhook_events(session_id: str) -> pd.DataFrame:
    """Get webhook events from database first, then fallback to files."""
    # Try database first
    db_events = get_webhook_events(session_id)
    if not db_events.empty:
        return db_events
    
    # Fallback to file-based events
    return get_webhook_events_from_file(session_id)


def get_backtest_results_from_files(session_id: str) -> Dict[str, Any]:
    """Load backtest results from result files."""
    paths = get_project_paths()
    results_dir = paths["results"] / session_id
    
    results = {
        "session_id": session_id,
        "statistics": {},
        "trades": [],
        "webhooks": [],
    }
    
    # Look for the results JSON
    for json_file in results_dir.glob("*.json"):
        if json_file.name != "config.json":
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    results["statistics"] = data.get("Statistics", {})
                    results["runtime"] = data.get("RuntimeStatistics", {})
            except Exception:
                pass
    
    # Load webhook log
    webhook_log = results_dir / "webhook_log.txt"
    if webhook_log.exists():
        try:
            with open(webhook_log, 'r') as f:
                results["webhooks"] = f.readlines()
        except Exception:
            pass
    
    return results


# ==================== UI Components ====================

def render_strategy_params_editor(current_params: Dict[str, Any]) -> Dict[str, Any]:
    """Render editable strategy parameters."""
    
    st.subheader("📊 Strategy Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**RSI Settings**")
        rsi_period = st.number_input(
            "RSI Period",
            min_value=5, max_value=50,
            value=current_params.get("rsi_period", 14),
            help="Number of periods for RSI calculation"
        )
        rsi_oversold = st.number_input(
            "RSI Oversold",
            min_value=10.0, max_value=50.0,
            value=float(current_params.get("rsi_oversold", 30.0)),
            help="RSI level below which asset is considered oversold"
        )
        rsi_overbought = st.number_input(
            "RSI Overbought",
            min_value=50.0, max_value=90.0,
            value=float(current_params.get("rsi_overbought", 70.0)),
            help="RSI level above which asset is considered overbought"
        )
    
    with col2:
        st.write("**Bollinger Bands**")
        bb_period = st.number_input(
            "BB Period",
            min_value=5, max_value=50,
            value=current_params.get("bb_period", 20),
            help="Number of periods for Bollinger Bands"
        )
        bb_std_dev = st.number_input(
            "BB Std Dev",
            min_value=1.0, max_value=4.0,
            value=float(current_params.get("bb_std_dev", 2.0)),
            step=0.1,
            help="Standard deviation multiplier for bands"
        )
    
    with col3:
        st.write("**Risk Management**")
        
        # Stop Loss % - User enters as decimal (e.g., 1.5 for 1.5%), we convert to 0.015
        current_stop_loss = float(current_params.get("stop_loss_pct", 0.02)) * 100  # Convert to display format
        
        stop_loss_input = st.number_input(
            "Stop Loss %",
            min_value=0.5,
            max_value=5.0,
            value=current_stop_loss,
            step=0.25,
            format="%.2f",
            help="Stop loss percentage from entry (e.g., 1.5 for 1.5%)"
        )
        stop_loss_pct = stop_loss_input / 100  # Convert to decimal format for algorithm
        
        # Take Profit % - User enters as decimal (e.g., 2.5 for 2.5%), we convert to 0.025
        current_take_profit = float(current_params.get("take_profit_pct", 0.025)) * 100  # Convert to display format
        
        take_profit_input = st.number_input(
            "Take Profit %",
            min_value=0.5,
            max_value=10.0,
            value=current_take_profit,
            step=0.25,
            format="%.2f",
            help="Take profit percentage from entry (e.g., 2.5 for 2.5%)"
        )
        take_profit_pct = take_profit_input / 100  # Convert to decimal format for algorithm
    
    return {
        "rsi_period": rsi_period,
        "rsi_oversold": rsi_oversold,
        "rsi_overbought": rsi_overbought,
        "bb_period": bb_period,
        "bb_std_dev": bb_std_dev,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
    }


def render_backtest_config_editor(current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Render editable backtest configuration."""
    
    st.subheader("📅 Backtest Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.strptime(current_config.get("start_date", "2024-01-01"), "%Y-%m-%d"),
            help="Backtest start date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.strptime(current_config.get("end_date", "2024-12-31"), "%Y-%m-%d"),
            help="Backtest end date"
        )
    
    with col3:
        initial_cash = st.number_input(
            "Initial Capital ($)",
            min_value=1000.0,
            max_value=10000000.0,
            value=float(current_config.get("initial_cash", 100000)),
            step=10000.0,
            help="Starting capital for backtest"
        )
    
    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "initial_cash": initial_cash,
    }


def render_webhook_monitor(session_id: str):
    """Render real-time webhook event monitor."""
    
    st.subheader("📡 Webhook Events Monitor")
    
    if not session_id:
        st.info("Select a backtest session to view webhook events")
        return
    
    paths = get_project_paths()
    webhook_log = paths["results"] / session_id / "webhook_log.txt"
    
    # Auto-refresh control
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.caption(f"Session: `{session_id}`")
    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=False, key="webhook_auto_refresh")
    with col3:
        refresh_interval = st.selectbox("Interval", [2, 5, 10], index=0, key="refresh_interval")
    
    if auto_refresh:
        st.caption(f"Refreshing every {refresh_interval} seconds...")
        time.sleep(refresh_interval)
        st.rerun()
    
    # Get webhook events (from DB or file)
    events_df = get_all_webhook_events(session_id)
    
    # Fallback to raw file reading if parsed events are empty
    if events_df.empty and webhook_log.exists():
        with open(webhook_log, 'r') as f:
            lines = f.readlines()
        
        if lines:
            # Summary stats from raw lines
            signal_count = sum(1 for l in lines if "SIGNAL" in l)
            scheduled_count = sum(1 for l in lines if "SCHEDULED" in l)
            alert_count = sum(1 for l in lines if "ALERT" in l)
            status_count = sum(1 for l in lines if "STATUS" in l)
            
            # Display metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("📊 Total", len(lines))
            col2.metric("🎯 Signals", signal_count)
            col3.metric("⏰ Scheduled", scheduled_count)
            col4.metric("⚠️ Alerts", alert_count)
            col5.metric("ℹ️ Status", status_count)
            
            st.divider()
            
            # Filter and view options
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                filter_type = st.selectbox(
                    "Filter by Type",
                    ["All", "SIGNAL", "SCHEDULED", "ALERT", "STATUS"],
                    index=0,
                    key="webhook_filter"
                )
            with col2:
                show_count = st.selectbox(
                    "Show Last",
                    [25, 50, 100, 200],
                    index=1,
                    key="webhook_count"
                )
            with col3:
                view_mode = st.radio(
                    "View",
                    ["Table", "Raw Log"],
                    horizontal=True,
                    key="webhook_view"
                )
            
            # Filter lines
            filtered_lines = lines
            if filter_type != "All":
                filtered_lines = [l for l in lines if filter_type in l]
            
            if view_mode == "Table":
                # Parse into table format
                parsed_events = []
                for line in reversed(filtered_lines[-show_count:]):
                    if "[WEBHOOK" in line:
                        parts = line.split("|")
                        event = {
                            "Time": line[:19] if len(line) > 19 else "",
                            "Type": "UNKNOWN",
                            "Symbol": "",
                            "Price": "",
                            "Reason": ""
                        }
                        
                        if len(parts) >= 1:
                            if "SIGNAL" in parts[0]:
                                event["Type"] = "🎯 SIGNAL"
                            elif "SCHEDULED" in parts[0]:
                                event["Type"] = "⏰ SCHEDULED"
                            elif "ALERT" in parts[0]:
                                event["Type"] = "⚠️ ALERT"
                            elif "STATUS" in parts[0]:
                                event["Type"] = "ℹ️ STATUS"
                        
                        if len(parts) >= 2:
                            symbol_price = parts[1].strip()
                            if "@" in symbol_price:
                                sp = symbol_price.split("@")
                                event["Symbol"] = sp[0].strip()
                                event["Price"] = sp[1].strip() if len(sp) > 1 else ""
                        
                        if len(parts) >= 3:
                            event["Reason"] = parts[2].strip()
                        
                        parsed_events.append(event)
                
                if parsed_events:
                    events_table = pd.DataFrame(parsed_events)
                    st.dataframe(events_table, use_container_width=True, hide_index=True)
                else:
                    st.info("No events match the current filter")
            else:
                # Raw log view
                st.text_area(
                    "Webhook Log (Most Recent First)",
                    value="\n".join(reversed(filtered_lines[-show_count:])),
                    height=400,
                    disabled=True
                )
            
            # Download button
            st.download_button(
                "📥 Download Full Log",
                data="\n".join(lines),
                file_name=f"webhook_log_{session_id}.txt",
                mime="text/plain"
            )
        else:
            st.info("No webhook events recorded yet")
    elif not events_df.empty:
        # Show from DataFrame
        st.dataframe(events_df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No webhook data found for session: {session_id}")


def render_backtest_history():
    """Render backtest run history table."""
    
    st.subheader("📜 Backtest History")
    
    # Get runs from database
    runs_df = get_backtest_runs_from_db(limit=20)
    
    if runs_df.empty:
        # Fallback: check results folder
        paths = get_project_paths()
        results_dir = paths["results"]
        
        if results_dir.exists():
            sessions = []
            for session_dir in sorted(results_dir.iterdir(), reverse=True)[:20]:
                if session_dir.is_dir() and session_dir.name.startswith("BT_"):
                    config_file = session_dir / "config.json"
                    status = "Completed" if (session_dir / "webhook_log.txt").exists() else "Unknown"
                    sessions.append({
                        "RunID": session_dir.name,
                        "AlgorithmName": "TQQQScalpingAlgorithm",
                        "Status": status,
                        "StartTime": datetime.fromtimestamp(session_dir.stat().st_mtime),
                    })
            
            if sessions:
                runs_df = pd.DataFrame(sessions)
    
    if not runs_df.empty:
        # Status icons
        status_icons = {
            "Completed": "✅",
            "Failed": "❌",
            "Running": "🔄",
            "Unknown": "❓"
        }
        
        display_df = runs_df.copy()
        display_df["Status"] = display_df["Status"].apply(
            lambda x: f"{status_icons.get(x, '❓')} {x}"
        )
        
        if "StartTime" in display_df.columns:
            display_df["StartTime"] = pd.to_datetime(display_df["StartTime"]).dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Session selector for webhook viewing
        session_options = runs_df["RunID"].tolist()
        if session_options:
            selected_session = st.selectbox(
                "Select session to view webhooks",
                options=[""] + session_options,
                index=0
            )
            if selected_session:
                st.session_state["selected_backtest_session"] = selected_session
    else:
        st.info("No backtest runs recorded yet.")


def run_backtest_in_background(params: Dict[str, Any], session_id: str) -> None:
    """Start a backtest run (called via MCP or direct LEAN)."""
    # This would typically call the MCP tool or direct LEAN runner
    # For now, store the command that would be run
    pass


# ==================== Main Render Function ====================

def render_backtest_runner():
    """Main render function for the Backtest Runner page."""
    st.title("🚀 Backtest Runner")
    
    st.caption("Run backtests, update parameters, and monitor webhooks in real-time")
    
    # Initialize session state
    if "backtest_params" not in st.session_state:
        st.session_state["backtest_params"] = load_saved_params()
    
    if "running_backtest" not in st.session_state:
        st.session_state["running_backtest"] = False
    
    if "selected_backtest_session" not in st.session_state:
        st.session_state["selected_backtest_session"] = ""
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚙️ Parameters", 
        "▶️ Run Backtest", 
        "📡 Webhook Monitor",
        "📜 History"
    ])
    
    # ==================== Tab 1: Parameters ====================
    with tab1:
        current_params = st.session_state["backtest_params"]
        
        # Strategy params
        strategy_params = render_strategy_params_editor(current_params)
        
        st.divider()
        
        # Backtest config
        backtest_config = render_backtest_config_editor(current_params)
        
        st.divider()
        
        # Webhook settings
        st.subheader("📡 Webhook Settings")
        col1, col2 = st.columns(2)
        with col1:
            webhook_interval = st.number_input(
                "Webhook Interval (minutes)",
                min_value=1, max_value=60,
                value=current_params.get("webhook_interval_minutes", 5),
                help="How often scheduled webhooks fire during backtest"
            )
        with col2:
            enable_signal_webhooks = st.checkbox(
                "Enable Signal Webhooks",
                value=True,
                help="Log webhooks when trading signals are detected"
            )
        
        # Combine all params
        all_params = {**strategy_params, **backtest_config, 
                      "webhook_interval_minutes": webhook_interval,
                      "enable_signal_webhooks": enable_signal_webhooks}
        
        # Save/Reset buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 Save Settings", type="primary"):
                st.session_state["backtest_params"] = all_params
                if save_params_to_config(all_params):
                    st.success("Settings saved!")
                    st.rerun()
        
        with col2:
            if st.button("🔄 Reset to Defaults"):
                st.session_state["backtest_params"] = {**DEFAULT_STRATEGY_PARAMS, **DEFAULT_BACKTEST_CONFIG}
                st.rerun()
        
        # Show current config as JSON (collapsible)
        with st.expander("📋 View Current Config (JSON)"):
            st.json(all_params)
    
    # ==================== Tab 2: Run Backtest ====================
    with tab2:
        st.subheader("▶️ Execute Backtest")
        
        params = st.session_state["backtest_params"]
        
        # Check execution environment
        paths = get_project_paths()
        
        # Check for built LEAN
        lean_launcher = paths["lean"] / "Launcher" / "bin" / "Release" / "QuantConnect.Lean.Launcher.exe"
        lean_launcher_debug = paths["lean"] / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.exe"
        lean_launcher_net6 = paths["lean"] / "Launcher" / "bin" / "Release" / "net6.0" / "QuantConnect.Lean.Launcher.exe"
        lean_built = lean_launcher.exists() or lean_launcher_debug.exists() or lean_launcher_net6.exists()
        
        if not lean_built:
            st.error("❌ **LEAN Engine not compiled!**")
            st.markdown("""
            **To compile LEAN locally:**
            
            1. **Install .NET 8 SDK** (if not installed):
               - Download from: https://dotnet.microsoft.com/download/dotnet/8.0
            
            2. **Build LEAN** by running the build script:
               ```powershell
               .\\build_lean.ps1
               ```
               
               Or manually:
               ```powershell
               cd quantconnect-lean
               dotnet build QuantConnect.Lean.sln -c Release
               ```
            """)
            st.stop()
        
        # Show LEAN status
        st.success("✅ LEAN Engine is compiled and ready!")
        
        st.divider()
        
        # Initialize override state
        if "use_parameter_override" not in st.session_state:
            st.session_state["use_parameter_override"] = False
        
        # Main toggle for parameter override
        use_override = st.toggle(
            "🔧 **Use Parameter Override** (customize settings for this run only)",
            value=st.session_state.get("use_parameter_override", False),
            key="toggle_override",
            help="When ON: Use custom parameters below. When OFF: Use saved parameters from the Parameters tab."
        )
        st.session_state["use_parameter_override"] = use_override
        
        if not use_override:
            # Show summary of saved parameters that will be used
            st.info(f"""
            **Using Saved Parameters from Parameters Tab:**
            - RSI: Period={params.get('rsi_period', 14)}, Oversold={params.get('rsi_oversold', 30)}, Overbought={params.get('rsi_overbought', 70)}
            - Bollinger: Period={params.get('bb_period', 20)}, Std Dev={params.get('bb_std_dev', 2.0)}
            - Risk: Stop Loss={float(params.get('stop_loss_pct', 0.02))*100:.2f}%, Take Profit={float(params.get('take_profit_pct', 0.025))*100:.2f}%
            - Dates: {params.get('start_date', '2024-01-01')} to {params.get('end_date', '2024-12-31')}
            - Capital: ${float(params.get('initial_cash', 100000)):,.0f}
            """)
            
            # Use saved parameters
            run_params = {
                "start_date": params.get("start_date", "2024-01-01"),
                "end_date": params.get("end_date", "2024-12-31"),
                "initial_cash": float(params.get("initial_cash", 100000)),
                "rsi_period": int(params.get("rsi_period", 14)),
                "rsi_oversold": float(params.get("rsi_oversold", 30)),
                "rsi_overbought": float(params.get("rsi_overbought", 70)),
                "bb_period": int(params.get("bb_period", 20)),
                "bb_std_dev": float(params.get("bb_std_dev", 2.0)),
                "stop_loss_pct": float(params.get("stop_loss_pct", 0.02)),
                "take_profit_pct": float(params.get("take_profit_pct", 0.025)),
            }
        else:
            # Show override form
            with st.container(border=True):
                st.caption("⚠️ These parameters are for this run only and will NOT be saved.")
                
                st.write("**RSI Settings**")
                override_col1, override_col2, override_col3 = st.columns(3)
                with override_col1:
                    override_rsi_period = st.number_input(
                        "RSI Period",
                        min_value=5, max_value=50,
                        value=int(params.get('rsi_period', 14)),
                        key="override_rsi_period",
                        help="Number of periods for RSI calculation"
                    )
                with override_col2:
                    override_rsi_oversold = st.number_input(
                        "RSI Oversold",
                        min_value=10.0, max_value=50.0,
                        value=float(params.get('rsi_oversold', 30)),
                        key="override_rsi_oversold",
                        help="RSI level below which asset is considered oversold"
                    )
                with override_col3:
                    override_rsi_overbought = st.number_input(
                        "RSI Overbought",
                        min_value=50.0, max_value=90.0,
                        value=float(params.get('rsi_overbought', 70)),
                        key="override_rsi_overbought",
                        help="RSI level above which asset is considered overbought"
                    )
                
                st.write("**Bollinger Bands**")
                bb_col1, bb_col2 = st.columns(2)
                with bb_col1:
                    override_bb_period = st.number_input(
                        "BB Period",
                        min_value=5, max_value=50,
                        value=int(params.get('bb_period', 20)),
                        key="override_bb_period",
                        help="Number of periods for Bollinger Bands"
                    )
                with bb_col2:
                    override_bb_std_dev = st.number_input(
                        "BB Std Dev",
                        min_value=1.0, max_value=4.0,
                        value=float(params.get('bb_std_dev', 2.0)),
                        step=0.1,
                        key="override_bb_std_dev",
                        help="Standard deviation multiplier for bands"
                    )
                
                st.write("**Risk Management**")
                risk_col1, risk_col2 = st.columns(2)
                
                with risk_col1:
                    # Stop Loss % - User enters as decimal (e.g., 1.5 for 1.5%), we convert to 0.015
                    current_stop_loss = float(params.get('stop_loss_pct', 0.02)) * 100
                    
                    stop_loss_input = st.number_input(
                        "Stop Loss %",
                        min_value=0.5,
                        max_value=5.0,
                        value=current_stop_loss,
                        step=0.25,
                        format="%.2f",
                        key="override_stop_loss",
                        help="Stop loss percentage from entry (e.g., 1.5 for 1.5%)"
                    )
                    override_stop_loss = stop_loss_input / 100
                    
                with risk_col2:
                    # Take Profit % - User enters as decimal (e.g., 2.5 for 2.5%), we convert to 0.025
                    current_take_profit = float(params.get('take_profit_pct', 0.025)) * 100
                    
                    take_profit_input = st.number_input(
                        "Take Profit %",
                        min_value=0.5,
                        max_value=10.0,
                        value=current_take_profit,
                        step=0.25,
                        format="%.2f",
                        key="override_take_profit",
                        help="Take profit percentage from entry (e.g., 2.5 for 2.5%)"
                    )
                
                st.write("**Backtest Configuration**")
                config_col1, config_col2, config_col3 = st.columns(3)
                with config_col1:
                    override_start = st.date_input(
                        "Start Date",
                        value=datetime.strptime(params.get("start_date", "2024-01-01"), "%Y-%m-%d"),
                        key="override_start",
                        help="Backtest start date"
                    )
                with config_col2:
                    override_end = st.date_input(
                        "End Date",
                        value=datetime.strptime(params.get("end_date", "2024-12-31"), "%Y-%m-%d"),
                        key="override_end",
                        help="Backtest end date"
                    )
                with config_col3:
                    override_cash = st.number_input(
                        "Initial Cash ($)",
                        value=float(params.get("initial_cash", 100000)),
                        step=10000.0,
                        key="override_cash",
                        help="Starting capital for backtest"
                    )
            
            # Use override parameters
            run_params = {
                "start_date": override_start.strftime("%Y-%m-%d"),
                "end_date": override_end.strftime("%Y-%m-%d"),
                "initial_cash": override_cash,
                "rsi_period": override_rsi_period,
                "rsi_oversold": override_rsi_oversold,
                "rsi_overbought": override_rsi_overbought,
                "bb_period": override_bb_period,
                "bb_std_dev": override_bb_std_dev,
                "stop_loss_pct": override_stop_loss,
                "take_profit_pct": override_take_profit,
            }
        
        st.divider()
        # Run buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            run_clicked = st.button(
                "🚀 Run Backtest",
                type="primary",
                disabled=st.session_state.get("running_backtest", False)
            )
        
        with col2:
            if st.session_state.get("running_backtest", False):
                if st.button("⏹️ Stop", type="secondary"):
                    st.session_state["running_backtest"] = False
                    st.rerun()
        
        if run_clicked:
            session_id = generate_session_id()
            st.session_state["current_session_id"] = session_id
            st.session_state["selected_backtest_session"] = session_id
            
            # Show configuration summary
            st.info(f"""
            **Backtest Configuration:**
            - Session ID: `{session_id}`
            - Date Range: {run_params['start_date']} to {run_params['end_date']}
            - Initial Capital: ${run_params['initial_cash']:,.0f}
            - RSI: Period={run_params['rsi_period']}, Oversold={run_params['rsi_oversold']}, Overbought={run_params['rsi_overbought']}
            - BB: Period={run_params['bb_period']}, Std Dev={run_params['bb_std_dev']}
            - Stop Loss: {run_params['stop_loss_pct']*100:.1f}%, Take Profit: {run_params['take_profit_pct']*100:.1f}%
            """)
            
            # Run using local LEAN engine via Python script
            paths = get_project_paths()
            backtest_script = paths["backtest"] / "backtest_runner.py"
            
            # Create session results directory
            results_path = paths["results"] / session_id
            results_path.mkdir(parents=True, exist_ok=True)
            
            # Save config for this run
            config = {
                "session_id": session_id,
                "parameters": {
                    "start-date": run_params['start_date'],
                    "end-date": run_params['end_date'],
                    "cash": str(run_params['initial_cash']),
                    "rsi-period": str(run_params['rsi_period']),
                    "rsi-oversold": str(run_params['rsi_oversold']),
                    "rsi-overbought": str(run_params['rsi_overbought']),
                    "bb-period": str(run_params['bb_period']),
                    "bb-std-dev": str(run_params['bb_std_dev']),
                    "stop-loss-pct": str(run_params['stop_loss_pct']),
                    "take-profit-pct": str(run_params['take_profit_pct']),
                }
            }
            
            config_file = results_path / "config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            st.session_state["running_backtest"] = True
            
            # Create a placeholder for live webhook updates
            webhook_placeholder = st.empty()
            output_placeholder = st.empty()
            
            # Run backtest asynchronously using Popen for real-time output
            try:
                # NOTE: Do NOT set PYTHONHOME/PYTHONPATH here - that breaks the Python interpreter!
                # The backtest_runner.py script sets these env vars only when calling LEAN.
                import os
                env = os.environ.copy()
                
                # Only set PYTHONNET_PYDLL - this is read by backtest_runner.py 
                # but doesn't break Python itself
                python_paths = [
                    (r"C:\Users\anand\AppData\Local\Programs\Python\Python311", "python311.dll"),
                    (r"C:\Users\anand\AppData\Local\Programs\Python\Python310", "python310.dll"),
                    (r"C:\Users\anand\AppData\Local\Programs\Python\Python39", "python39.dll"),
                ]
                
                for home, dll_name in python_paths:
                    dll_path = os.path.join(home, dll_name)
                    if os.path.exists(dll_path):
                        # Only set PYTHONNET_PYDLL - backtest_runner.py handles the rest
                        env["PYTHONNET_PYDLL"] = dll_path
                        st.info(f"Using Python 3.11 for LEAN: {home}")
                        break
                
                process = subprocess.Popen(
                    ["python", str(backtest_script),
                     "--start", run_params['start_date'],
                     "--end", run_params['end_date'],
                     "--cash", str(run_params['initial_cash']),
                     "--rsi-period", str(run_params['rsi_period']),
                     "--rsi-oversold", str(run_params['rsi_oversold']),
                     "--rsi-overbought", str(run_params['rsi_overbought']),
                     "--bb-period", str(run_params['bb_period']),
                     "--bb-std-dev", str(run_params['bb_std_dev']),
                     "--stop-loss", str(run_params['stop_loss_pct']),
                     "--take-profit", str(run_params['take_profit_pct']),
                     "--session-id", session_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(paths["project_root"]),
                    env=env
                )
                
                # Monitor webhook log file while backtest runs
                webhook_log_path = results_path / "webhook_log.txt"
                all_output = []
                last_webhook_count = 0
                
                # Create persistent UI elements
                status_placeholder = output_placeholder.empty()
                output_area = st.empty()
                webhook_placeholder = st.empty()
                
                status_placeholder.info("🔄 Running backtest...")
                
                # Use a thread to read output non-blocking
                import queue
                output_queue = queue.Queue()
                
                def read_output(proc, q):
                    try:
                        for line in iter(proc.stdout.readline, ''):
                            if line:
                                q.put(line)
                            if proc.poll() is not None:
                                break
                    except:
                        pass
                
                output_thread = threading.Thread(target=read_output, args=(process, output_queue))
                output_thread.daemon = True
                output_thread.start()
                
                last_webhook_update = time.time()
                
                while process.poll() is None or not output_queue.empty():
                    # Read any available output from queue
                    try:
                        while True:
                            try:
                                line = output_queue.get_nowait()
                                all_output.append(line)
                            except queue.Empty:
                                break
                    except:
                        pass
                    
                    # Update webhook display frequently
                    if time.time() - last_webhook_update > 0.3:
                        last_webhook_update = time.time()
                        
                        if all_output:
                            output_area.code("".join(all_output[-20:]), language="text")
                        
                        # Check webhook log
                        if webhook_log_path.exists():
                            try:
                                with open(webhook_log_path, 'r') as f:
                                    webhook_lines = f.readlines()
                                
                                if len(webhook_lines) > last_webhook_count:
                                    last_webhook_count = len(webhook_lines)
                                    trading_events = [l for l in webhook_lines if "SIGNAL" in l]
                                    
                                    with webhook_placeholder.container():
                                        st.subheader("📡 Live Webhook Events")
                                        buy_count = sum(1 for l in trading_events if "BUY" in l.upper())
                                        profit_count = sum(1 for l in trading_events if "TAKE_PROFIT" in l.upper())
                                        stop_count = sum(1 for l in trading_events if "STOP_LOSS" in l.upper())
                                        
                                        cols = st.columns(4)
                                        cols[0].metric("🟢 Buy", buy_count)
                                        cols[1].metric("🔴 Exit", profit_count + stop_count)
                                        cols[2].metric("💰 Take Profit", profit_count)
                                        cols[3].metric("🛑 Stop Loss", stop_count)
                                        
                                        st.caption("Recent signals:")
                                        for wline in reversed(trading_events[-10:]):
                                            if "BUY" in wline.upper():
                                                st.success(f"🟢 {wline.strip()}")
                                            elif "TAKE_PROFIT" in wline.upper():
                                                st.info(f"💰 {wline.strip()}")
                                            elif "STOP_LOSS" in wline.upper():
                                                st.warning(f"🛑 {wline.strip()}")
                                            else:
                                                st.text(wline.strip())
                            except:
                                pass
                    
                    time.sleep(0.1)
                
                # Get any remaining buffered output (process is done, so no timeout needed)
                try:
                    remaining_output, _ = process.communicate(timeout=5)
                    if remaining_output:
                        all_output.append(remaining_output)
                except subprocess.TimeoutExpired:
                    # Process done but output still buffered - just continue
                    try:
                        process.kill()
                    except:
                        pass
                
                status_placeholder.empty()
                
                # Store results - success based on actual return code
                st.session_state["last_backtest_result"] = {
                    "success": process.returncode == 0,
                    "return_code": process.returncode,
                    "output": "".join(all_output),
                    "session_id": session_id,
                    "results_path": str(results_path),
                    "webhook_log_path": str(webhook_log_path)
                }
                
                # Show success immediately with balloons
                if process.returncode == 0:
                    st.balloons()
                    
            except subprocess.TimeoutExpired:
                st.session_state["last_backtest_result"] = {"success": False, "error": "Backtest process timeout (>15 min)"}
                try:
                    process.kill()
                except:
                    pass
            except Exception as e:
                st.session_state["last_backtest_result"] = {"success": False, "error": str(e)}
            finally:
                st.session_state["running_backtest"] = False
                st.rerun()  # Force rerun to show results
        
        # Show last backtest result if available
        if "last_backtest_result" in st.session_state and st.session_state["last_backtest_result"]:
            result = st.session_state["last_backtest_result"]
            
            if "error" in result:
                st.error(f"❌ **Backtest failed:** {result['error']}")
            elif result.get("success"):
                st.success("✅ **Backtest completed successfully!**")
            else:
                st.error(f"❌ **Backtest failed!** (exit code: {result.get('return_code', 'unknown')})")
            
            # Show webhook summary
            webhook_log_path = Path(result.get("webhook_log_path", ""))
            if webhook_log_path.exists():
                with open(webhook_log_path, 'r') as f:
                    webhook_lines = f.readlines()
                
                trading_signals = [l for l in webhook_lines if "SIGNAL" in l]
                buy_count = sum(1 for l in trading_signals if "BUY" in l.upper())
                profit_count = sum(1 for l in trading_signals if "TAKE_PROFIT" in l.upper())
                stop_count = sum(1 for l in trading_signals if "STOP_LOSS" in l.upper())
                # Sell/Exit = all exits (take profit + stop loss)
                exit_count = profit_count + stop_count
                
                st.subheader("📡 Webhook Events")
                cols = st.columns(4)
                cols[0].metric("🟢 Buy", buy_count)
                cols[1].metric("🔴 Exit", exit_count)
                cols[2].metric("💰 Take Profit", profit_count)
                cols[3].metric("🛑 Stop Loss", stop_count)
                
                # Show signals
                with st.expander(f"📋 View {len(trading_signals)} trading signals", expanded=True):
                    for line in reversed(trading_signals[-50:]):
                        if "BUY" in line.upper():
                            st.success(f"🟢 {line.strip()}")
                        elif "TAKE_PROFIT" in line.upper():
                            st.info(f"💰 {line.strip()}")
                        elif "STOP_LOSS" in line.upper():
                            st.warning(f"🛑 {line.strip()}")
                        elif "SELL" in line.upper():
                            st.error(f"🔴 {line.strip()}")
                        else:
                            st.text(line.strip())
            
            # Show output
            if "output" in result:
                with st.expander("LEAN Output", expanded=False):
                    output = result["output"]
                    st.code(output[-5000:] if len(output) > 5000 else output)
            
            # Show results path
            results_path = Path(result.get("results_path", ""))
            if results_path.exists():
                for json_file in results_path.glob("*.json"):
                    if json_file.name != "config.json":
                        st.info(f"📊 Results: {json_file.name}")
                
                st.info(f"💡 View details in **History** tab. Session: `{result.get('session_id', '')}`")
            
            # Clear button
            if st.button("🗑️ Clear Results"):
                st.session_state["last_backtest_result"] = None
                st.rerun()
        
        # Quick run presets
        st.divider()
        st.subheader("⚡ Quick Run Presets")
        
        preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
        
        with preset_col1:
            if st.button("📅 Last 30 Days", use_container_width=True):
                end = datetime.now()
                start = end - timedelta(days=30)
                # Update backtest_params which feeds the widgets
                st.session_state["backtest_params"]["start_date"] = start.strftime("%Y-%m-%d")
                st.session_state["backtest_params"]["end_date"] = end.strftime("%Y-%m-%d")
                st.rerun()
        
        with preset_col2:
            if st.button("📅 Last Quarter", use_container_width=True):
                end = datetime.now()
                start = end - timedelta(days=90)
                st.session_state["backtest_params"]["start_date"] = start.strftime("%Y-%m-%d")
                st.session_state["backtest_params"]["end_date"] = end.strftime("%Y-%m-%d")
                st.rerun()
        
        with preset_col3:
            if st.button("📅 YTD 2024", use_container_width=True):
                st.session_state["backtest_params"]["start_date"] = "2024-01-01"
                st.session_state["backtest_params"]["end_date"] = "2024-12-31"
                st.rerun()
        
        with preset_col4:
            if st.button("📅 Full Year 2023", use_container_width=True):
                st.session_state["backtest_params"]["start_date"] = "2023-01-01"
                st.session_state["backtest_params"]["end_date"] = "2023-12-31"
                st.rerun()
    
    # ==================== Tab 3: Webhook Monitor ====================
    with tab3:
        selected_session = st.session_state.get("selected_backtest_session", "")
        
        # Session selector
        paths = get_project_paths()
        results_dir = paths["results"]
        
        if results_dir.exists():
            sessions = [""]
            for session_dir in sorted(results_dir.iterdir(), reverse=True)[:20]:
                if session_dir.is_dir() and session_dir.name.startswith("BT_"):
                    sessions.append(session_dir.name)
            
            if len(sessions) > 1:
                selected = st.selectbox(
                    "Select Backtest Session",
                    options=sessions,
                    index=sessions.index(selected_session) if selected_session in sessions else 0
                )
                if selected:
                    st.session_state["selected_backtest_session"] = selected
                    selected_session = selected
        
        render_webhook_monitor(selected_session)
    
    # ==================== Tab 4: History ====================
    with tab4:
        render_backtest_history()
        
        st.divider()
        
        # Compare backtests section
        st.subheader("📊 Compare Backtests")
        
        runs_df = get_backtest_runs_from_db(limit=10)
        
        if not runs_df.empty:
            selected_runs = st.multiselect(
                "Select backtests to compare",
                options=runs_df["RunID"].tolist(),
                max_selections=5
            )
            
            if selected_runs and len(selected_runs) >= 2:
                st.info(f"Comparing {len(selected_runs)} backtests...")
                
                # Query database for comparison
                try:
                    db = get_db_connection()
                    if db and db.is_connected:
                        placeholders = ','.join('?' * len(selected_runs))
                        
                        # Get backtest outcomes for comparison
                        query = f"""
                        SELECT 
                            BacktestId,
                            TotalReturn,
                            SharpeRatio,
                            SortinoRatio,
                            MaxDrawdown,
                            WinRate,
                            ProfitFactor,
                            TotalTrades,
                            WinningTrades,
                            LosingTrades,
                            AverageWin,
                            AverageLoss,
                            LargestWin,
                            LargestLoss,
                            CAST(ParametersJson AS NVARCHAR(MAX)) AS Parameters
                        FROM BacktestOutcomes 
                        WHERE BacktestId IN ({placeholders})
                        ORDER BY TotalReturn DESC
                        """
                        
                        comparison_df = db.query(query, tuple(selected_runs))
                        
                        if not comparison_df.empty:
                            
                            # Format numeric columns as percentages
                            pct_cols = ['TotalReturn', 'MaxDrawdown', 'WinRate']
                            for col in pct_cols:
                                if col in comparison_df.columns:
                                    comparison_df[col] = comparison_df[col].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A")
                            
                            # Format ratio columns
                            ratio_cols = ['SharpeRatio', 'SortinoRatio', 'ProfitFactor']
                            for col in ratio_cols:
                                if col in comparison_df.columns:
                                    comparison_df[col] = comparison_df[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "N/A")
                            
                            # Format dollar amounts
                            dollar_cols = ['AverageWin', 'AverageLoss', 'LargestWin', 'LargestLoss']
                            for col in dollar_cols:
                                if col in comparison_df.columns:
                                    comparison_df[col] = comparison_df[col].apply(lambda x: f"${abs(x):,.2f}" if pd.notna(x) else "N/A")
                            
                            # Display comparison table (without Parameters column)
                            display_cols = [col for col in comparison_df.columns if col != 'Parameters']
                            st.dataframe(
                                comparison_df[display_cols],
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Show parameters in expandable sections
                            st.subheader("Parameters Comparison")
                            for _, row in comparison_df.iterrows():
                                with st.expander(f"📋 {row['BacktestId']}", expanded=False):
                                    try:
                                        params = json.loads(row['Parameters'])
                                        st.json(params)
                                    except:
                                        st.text(row['Parameters'])
                            
                            # Show MCP call example
                            with st.expander("💡 Call via MCP", expanded=False):
                                st.code(f"""
# To compare via MCP:
mcp_lean-ops_compare_backtests(session_ids={selected_runs})
                                """, language="python")
                        else:
                            st.warning("No backtest data found for selected sessions")
                    else:
                        st.error("Could not connect to database")
                        
                except Exception as e:
                    st.error(f"Error comparing backtests: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        else:
            st.info("Run some backtests first to enable comparison")


# Export for pages/__init__.py
render_backtest = render_backtest_runner



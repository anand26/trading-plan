"""
TQQQ/SQQQ Trading System - Backtest Runner
==========================================
Executes LEAN backtests and stores results in SQL for Trade-Mind MCP queries.

This is the bridge between LEAN engine and Trade-Mind MCP:
- Runs backtests with configurable parameters
- Parses LEAN output (JSON results, transaction logs)
- Stores trades, signals, and outcomes in SQL Server
- Makes data available to Trade-Mind MCP tools

Usage:
    python backtest_runner.py                          # Run with defaults
    python backtest_runner.py --start 2024-01-01      # Custom date range
    python backtest_runner.py --sweep                  # Parameter sweep mode
"""

import os
import sys
import json
import uuid
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pyodbc

# ============================================
# CONFIGURATION
# ============================================

@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""
    session_id: str
    start_date: str
    end_date: str
    initial_cash: float = 100000.0
    
    # ==========================================
    # STRATEGY TYPE
    # ==========================================
    algorithm_name: str = "TQQQSQQQPairsAlgorithm"  # or "TQQQScalpingAlgorithm"
    
    # ==========================================
    # PAIRS RATIO STRATEGY v3.0 PARAMETERS
    # ==========================================
    
    # Z-score lookback (number of 5-min bars)
    zscore_lookback: int = 50
    
    # Z-score thresholds
    entry_zscore: float = 1.5  # Enter when |Z| > this
    exit_zscore: float = 0.3   # Exit when |Z| < this
    stop_zscore: float = 3.0   # Stop if spread diverges
    
    # Position sizing
    position_size: float = 0.50  # 50% of portfolio
    
    # Risk management
    stop_loss_pct: float = 0.03  # 3% stop loss
    
    # Timing
    max_hold_minutes: int = 0    # 0 = no limit (intraday close)
    min_bars_between: int = 3    # Min bars between trades
    
    # ==========================================
    # LEGACY PARAMETERS (for TQQQScalpingAlgorithm)
    # ==========================================
    rsi_period: int = 14
    rsi_oversold: float = 28.0
    rsi_overbought: float = 72.0
    bb_period: int = 20
    bb_std_dev: float = 2.0
    position_size_level1: float = 0.50
    position_size_level2: float = 0.30
    position_size_level3: float = 0.20
    ema_fast_period: int = 9
    ema_slow_period: int = 21
    
    # Paths
    lean_path: str = ""
    algorithm_path: str = ""
    data_path: str = ""
    results_path: str = ""


class BacktestRunner:
    """
    Runs LEAN backtests and stores results for Trade-Mind MCP.
    
    Data Flow:
    1. LEAN Engine → JSON Results + Transaction Log
    2. This Runner → Parse Results
    3. SQL Server → Trades, BacktestOutcomes, Signals tables
    4. Trade-Mind MCP → Query SQL for get_last_trades, calculate_win_rate, etc.
    """
    
    def __init__(self, connection_string: str | None = None):
        self.base_path = Path(__file__).parent.parent
        self.lean_path = self.base_path / "quantconnect-lean"
        self.results_path = self.base_path / "backtest" / "results"
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        # Auto-sync algorithm files to LEAN folder
        self._sync_algorithm_files()
        
        # SQL Connection (for Trade-Mind MCP data)
        self.conn_string = connection_string or self._get_default_connection_string()
        self.conn: Optional[pyodbc.Connection] = None
    
    def _sync_algorithm_files(self) -> None:
        """Sync algorithm files from algorithms/ to quantconnect-lean/Algorithm.Python/"""
        import shutil
        
        source_algo_dir = self.base_path / "algorithms"
        target_algo_dir = self.lean_path / "Algorithm.Python"
        backtest_dir = self.base_path / "backtest"
        
        # Files to sync from algorithms/
        algo_files = ["TQQQScalpingAlgorithm.py", "TQQQSQQQPairsAlgorithm.py", "sql_connector.py"]
        
        for filename in algo_files:
            src = source_algo_dir / filename
            dst = target_algo_dir / filename
            if src.exists():
                shutil.copy2(src, dst)
                print(f"[SYNC] Copied {filename} to LEAN folder")
        
        # Sync webhook_simulator from backtest/
        webhook_src = backtest_dir / "webhook_simulator.py"
        webhook_dst = target_algo_dir / "webhook_simulator.py"
        if webhook_src.exists():
            shutil.copy2(webhook_src, webhook_dst)
            print(f"[SYNC] Copied webhook_simulator.py to LEAN folder")
    
    def _get_default_connection_string(self) -> str:
        """Default SQL Server connection string."""
        return (
            "Driver={ODBC Driver 17 for SQL Server};"
            "Server=localhost;"
            "Database=TradingDB;"
            "Trusted_Connection=yes;"
        )
    
    def connect_db(self) -> bool:
        """Connect to SQL Server database."""
        try:
            self.conn = pyodbc.connect(self.conn_string)
            print("[DB] Connected to TradingDB")
            return True
        except Exception as e:
            print(f"[DB] Connection failed: {e}")
            print("[DB] Results will be saved to files only")
            return False
    
    def generate_session_id(self, prefix: str = "BT") -> str:
        """Generate unique session ID for this backtest."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{short_uuid}"
    
    # ============================================
    # LEAN EXECUTION
    # ============================================
    
    def create_lean_config(self, config: BacktestConfig) -> Path:
        """Create LEAN config file for this backtest run."""
        
        # Determine algorithm name and file
        algo_name = getattr(config, 'algorithm_name', 'TQQQSQQQPairsAlgorithm')
        algo_file = f"{algo_name}.py"
        
        # Build parameters based on algorithm type
        if algo_name == "TQQQSQQQPairsAlgorithm":
            # Pairs Ratio Strategy v3.0
            parameters = {
                "start-date": config.start_date,
                "end-date": config.end_date,
                "cash": str(config.initial_cash),
                
                # Z-score parameters
                "zscore-lookback": str(config.zscore_lookback),
                "entry-zscore": str(config.entry_zscore),
                "exit-zscore": str(config.exit_zscore),
                "stop-zscore": str(config.stop_zscore),
                
                # Position sizing
                "position-size": str(config.position_size),
                
                # Risk management
                "stop-loss-pct": str(config.stop_loss_pct),
                
                # Timing
                "max-hold-minutes": str(config.max_hold_minutes),
                "min-bars-between": str(config.min_bars_between),
                
                # Session tracking
                "session-id": config.session_id,
            }
        else:
            # Legacy TQQQScalpingAlgorithm
            parameters = {
                "start-date": config.start_date,
                "end-date": config.end_date,
                "cash": str(config.initial_cash),
                "rsi-period": str(config.rsi_period),
                "rsi-oversold": str(config.rsi_oversold),
                "rsi-overbought": str(config.rsi_overbought),
                "bb-period": str(config.bb_period),
                "bb-std-dev": str(config.bb_std_dev),
                "position-size-level1": str(config.position_size_level1),
                "position-size-level2": str(config.position_size_level2),
                "position-size-level3": str(config.position_size_level3),
                "stop-loss-pct": str(config.stop_loss_pct),
                "ema-fast-period": str(config.ema_fast_period),
                "ema-slow-period": str(config.ema_slow_period),
                "session-id": config.session_id,
            }
        
        lean_config = {
            "environment": "backtesting",
            "algorithm-type-name": algo_name,
            "algorithm-language": "Python",
            "algorithm-location": str(self.lean_path / "Algorithm.Python" / algo_file),
            "data-folder": str(self.lean_path / "Data"),
            "parameters": parameters,
            
            # Results output
            "results-destination-folder": str(self.results_path / config.session_id),
            "transaction-log": str(self.results_path / config.session_id / "transactions.csv"),
            
            # Handlers
            "live-mode": False,
            "setup-handler": "QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler",
            "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler",
            "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
            "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",
            "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
        }
        
        # Create session results directory
        session_results_path = self.results_path / config.session_id
        session_results_path.mkdir(parents=True, exist_ok=True)
        
        # Write config
        config_path = session_results_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump(lean_config, f, indent=2)
        
        print(f"[CONFIG] Created: {config_path}")
        return config_path
    
    def run_lean_backtest(self, config_path: Path) -> Dict[str, Any]:
        """Execute LEAN backtest and return results."""
        launcher_path = self.lean_path / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.exe"
        
        # Check if LEAN is built
        if not launcher_path.exists():
            # Try Release build
            launcher_path = self.lean_path / "Launcher" / "bin" / "Release" / "QuantConnect.Lean.Launcher.exe"
        
        if not launcher_path.exists():
            print("[LEAN] Launcher not found. Building LEAN...")
            self._build_lean()
            launcher_path = self.lean_path / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.exe"
        
        print(f"[LEAN] Running backtest with config: {config_path}")
        
        try:
            # Set up environment for pythonnet
            env = os.environ.copy()
            
            # Find Python DLL - LEAN requires Python 3.8-3.11 (NOT 3.12 or 3.13!)
            # Check Python 3.11 first, then fall back to older versions
            python_home = None
            python_dll = None
            python_paths = [
                (r"C:\Users\anand\AppData\Local\Programs\Python\Python311", "python311.dll"),
                (r"C:\Users\anand\AppData\Local\Programs\Python\Python310", "python310.dll"),
                (r"C:\Users\anand\AppData\Local\Programs\Python\Python39", "python39.dll"),
                (r"C:\Python311", "python311.dll"),
                (r"C:\Python310", "python310.dll"),
            ]
            
            for home, dll_name in python_paths:
                dll_path = os.path.join(home, dll_name)
                if os.path.exists(dll_path):
                    python_home = home
                    python_dll = dll_path
                    break
            
            if python_dll and python_home:
                # Set all required environment variables for pythonnet
                env["PYTHONNET_PYDLL"] = python_dll
                env["PYTHONHOME"] = python_home
                env["PYTHONPATH"] = os.path.join(python_home, "Lib") + ";" + os.path.join(python_home, "DLLs")
                
                # Also update PATH to include Python directory
                env["PATH"] = python_home + ";" + env.get("PATH", "")
                
                print(f"[LEAN] Using Python DLL: {python_dll}")
                print(f"[LEAN] PYTHONHOME: {python_home}")
            else:
                print("[LEAN] WARNING: Could not find compatible Python DLL (3.8-3.11)!")
                print("[LEAN] Please install Python 3.11 from https://www.python.org/downloads/release/python-3119/")
            
            # Run LEAN with our config using Popen to handle hanging issue
            # LEAN sometimes doesn't close stdout properly, so we use polling
            # We discard stdout to prevent buffer blocking - we detect completion via files
            process = subprocess.Popen(
                [str(launcher_path), f"--config={config_path}"],
                cwd=str(self.lean_path / "Launcher"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            
            # Monitor for completion by checking for result files
            results_dir = Path(config_path).parent
            # LEAN creates {algorithm_name}.json as main result file
            # Read algorithm name from config
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            algo_name = cfg.get('algorithm-type-name', 'TQQQScalpingAlgorithm')
            result_file = results_dir / f"{algo_name}.json"
            log_file = results_dir / f"{algo_name}-log.txt"
            max_wait_time = 1800  # 30 minute max
            poll_interval = 2  # Check every 2 seconds
            waited = 0
            
            print(f"[LEAN] Monitoring for completion...")
            print(f"[LEAN] Looking for: {result_file}")
            
            import time
            while waited < max_wait_time:
                # Check if process exited on its own
                if process.poll() is not None:
                    print(f"[LEAN] Process exited with code: {process.returncode}")
                    break
                
                # Check if LEAN has created result file (indicates completion)
                if result_file.exists() and result_file.stat().st_size > 1000:
                    # Also check log file for completion message
                    log_complete = False
                    if log_file.exists():
                        try:
                            log_content = log_file.read_text(encoding='utf-8', errors='ignore')
                            if "Algorithm Id:" in log_content or "STATISTICS::" in log_content:
                                log_complete = True
                        except:
                            pass
                    
                    if log_complete:
                        print(f"[LEAN] Results file detected and log complete")
                        time.sleep(1)  # Brief pause to ensure files are written
                        
                        # Force terminate LEAN process
                        if process.poll() is None:
                            print("[LEAN] Terminating LEAN process (results complete)")
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=2)
                        break
                
                time.sleep(poll_interval)
                waited += poll_interval
                
                if waited % 30 == 0:
                    print(f"[LEAN] Still running... ({waited}s elapsed)")
            
            # Check for success - result files exist
            backtest_completed = result_file.exists() and result_file.stat().st_size > 1000
            
            if backtest_completed:
                print("[LEAN] Backtest completed successfully")
                return {"success": True, "stdout": ""}
            elif waited >= max_wait_time:
                print("[LEAN] Backtest timed out")
                if process.poll() is None:
                    process.kill()
                return {"success": False, "error": "Timeout waiting for results"}
            else:
                # Process exited but no results
                print("[LEAN] Process exited without creating results")
                return {"success": False, "error": "LEAN exited without results"}
            
        except Exception as e:
            print(f"[LEAN] Execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_lean(self):
        """Build LEAN solution if not already built."""
        sln_path = self.lean_path / "QuantConnect.Lean.sln"
        print(f"[BUILD] Building LEAN solution: {sln_path}")
        
        subprocess.run(
            ["dotnet", "build", str(sln_path), "-c", "Debug"],
            check=True
        )
    
    # ============================================
    # RESULTS PARSING (For Trade-Mind MCP)
    # ============================================
    
    def parse_backtest_results(self, session_id: str) -> Dict[str, Any]:
        """
        Parse LEAN backtest output files.
        
        This extracts data that Trade-Mind MCP needs:
        - Trades → sp_GetLastTrades, sp_CalculateWinRate
        - Statistics → sp_GetDailyPnL
        - Orders → BacktestOutcomes table
        """
        results_dir = self.results_path / session_id
        
        # Look for main algorithm results file - find any .json that's not config/data-monitor
        results_file = None
        for f in results_dir.glob("*.json"):
            if f.name not in ["config.json"] and "data-monitor" not in f.name and not f.name.endswith("-summary.json") and not f.name.endswith("-order-events.json"):
                results_file = f
                break
        
        if not results_file or not results_file.exists():
            print(f"[PARSE] No results file found in {results_dir}")
            return {}
        
        print(f"[PARSE] Reading results from: {results_file}")
        
        with open(results_file, 'r') as f:
            lean_results = json.load(f)
        
        # Extract key metrics for Trade-Mind MCP
        parsed = {
            "session_id": session_id,
            "statistics": self._extract_statistics(lean_results),
            "trades": self._extract_trades(lean_results),
            "orders": self._extract_orders(lean_results),
            "runtime_statistics": lean_results.get("RuntimeStatistics", {})
        }
        
        return parsed
    
    def _extract_statistics(self, results: Dict) -> Dict[str, float]:
        """Extract performance statistics from LEAN results.
        
        Handles both short and long backtests:
        - Short backtests: LEAN populates statistics and totalPerformance
        - Long backtests: LEAN may only populate runtimeStatistics, profitLoss, and charts
        """
        # LEAN uses lowercase keys in newer versions
        stats = results.get("statistics", results.get("Statistics", {}))
        runtime = results.get("runtimeStatistics", results.get("RuntimeStatistics", {}))
        
        # totalPerformance has the most accurate trade statistics (may be None for long backtests)
        total_perf = results.get("totalPerformance") or {}
        trade_stats = total_perf.get("tradeStatistics", {}) if total_perf else {}
        portfolio_stats = total_perf.get("portfolioStatistics", {}) if total_perf else {}
        
        # For long backtests, count trades from profitLoss or orders
        profit_loss = results.get("profitLoss", results.get("ProfitLoss", {}))
        orders = results.get("orders", results.get("Orders", {}))
        charts = results.get("charts", results.get("Charts", {}))
        
        # ============================================================
        # Calculate trade statistics from profitLoss when tradeStatistics is empty
        # ============================================================
        winning_trades = 0
        losing_trades = 0
        total_profit = 0.0
        total_loss = 0.0
        largest_win = 0.0
        largest_loss = 0.0
        
        if profit_loss and not trade_stats:
            for timestamp, pnl in profit_loss.items():
                if isinstance(pnl, (int, float)):
                    pnl_val = float(pnl)
                    if pnl_val > 0:
                        winning_trades += 1
                        total_profit += pnl_val
                        largest_win = max(largest_win, pnl_val)
                    elif pnl_val < 0:
                        losing_trades += 1
                        total_loss += abs(pnl_val)
                        largest_loss = max(largest_loss, abs(pnl_val))
        
        # Calculate trade count from available sources
        trade_count = 0
        if trade_stats.get("totalNumberOfTrades"):
            trade_count = self._parse_int(trade_stats.get("totalNumberOfTrades", 0))
        elif stats.get("Total Orders"):
            trade_count = self._parse_int(stats.get("Total Orders", 0))
        elif profit_loss:
            trade_count = len(profit_loss)
        elif orders:
            trade_count = len(orders)
        
        # If we calculated win/loss from profitLoss, use those values
        if profit_loss and not trade_stats:
            winning_trades_final = winning_trades
            losing_trades_final = losing_trades
        else:
            winning_trades_final = self._parse_int(trade_stats.get("numberOfWinningTrades", 0))
            losing_trades_final = self._parse_int(trade_stats.get("numberOfLosingTrades", 0))
        
        # Calculate win rate
        total_closed = winning_trades_final + losing_trades_final
        if trade_stats.get("winRate"):
            win_rate = self._parse_number(trade_stats.get("winRate", 0))
        elif stats.get("Win Rate"):
            win_rate = self._parse_pct(stats.get("Win Rate", "0%"))
        elif total_closed > 0:
            win_rate = winning_trades_final / total_closed
        else:
            win_rate = 0.0
        
        # ============================================================
        # Extract max drawdown from charts if stats is empty
        # ============================================================
        max_drawdown = 0.0
        if stats.get("Drawdown"):
            max_drawdown = self._parse_pct(stats.get("Drawdown", "0%"))
        elif charts:
            # Extract from Drawdown chart
            drawdown_chart = charts.get("Drawdown", charts.get("drawdown", {}))
            if drawdown_chart:
                series = drawdown_chart.get("series", drawdown_chart.get("Series", {}))
                equity_dd = series.get("Equity Drawdown", series.get("equity drawdown", {}))
                if equity_dd:
                    values = equity_dd.get("values", equity_dd.get("Values", []))
                    if values:
                        # Values are [timestamp, drawdown_pct] pairs
                        # Chart values are already percentages (like -32.85 for 32.85% drawdown)
                        # Convert to decimal (0.3285) to match _parse_pct format
                        dd_values = [v[1] for v in values if isinstance(v, list) and len(v) > 1]
                        if dd_values:
                            max_drawdown = abs(min(dd_values)) / 100.0  # Convert to decimal
                            print(f"[STATS] Max drawdown from chart: {max_drawdown * 100:.2f}%")
        
        # ============================================================
        # Calculate profit factor
        # ============================================================
        if trade_stats.get("profitFactor"):
            profit_factor = self._parse_number(trade_stats.get("profitFactor", 0))
        elif stats.get("Profit-Loss Ratio"):
            profit_factor = self._parse_number(stats.get("Profit-Loss Ratio", 0))
        elif total_loss > 0:
            profit_factor = total_profit / total_loss
        else:
            profit_factor = 0.0
        
        # Debug output
        print(f"[STATS] Extracting from LEAN results...")
        print(f"[STATS] statistics available: {bool(stats)}")
        print(f"[STATS] runtimeStatistics available: {bool(runtime)}")
        print(f"[STATS] totalPerformance available: {bool(total_perf)}")
        print(f"[STATS] profitLoss entries: {len(profit_loss)}")
        print(f"[STATS] orders entries: {len(orders)}")
        print(f"[STATS] Calculated from profitLoss: wins={winning_trades}, losses={losing_trades}")
        
        # ============================================================
        # Calculate performance metrics from equity curve
        # ============================================================
        # ALWAYS calculate from equity curve - LEAN's built-in stats are often wrong
        # (e.g., 1.75% volatility for TQQQ is impossible, Sharpe doesn't match returns)
        cagr = 0
        sharpe_ratio = 0
        sortino_ratio = 0
        volatility = 0
        calmar_ratio = 0
        
        if charts:
            equity_metrics = self._calculate_metrics_from_equity_curve(charts)
            if equity_metrics:
                cagr = equity_metrics.get("cagr", 0)
                sharpe_ratio = equity_metrics.get("sharpe_ratio", 0)
                sortino_ratio = equity_metrics.get("sortino_ratio", 0)
                volatility = equity_metrics.get("volatility", 0)
                if max_drawdown > 0:
                    calmar_ratio = cagr / max_drawdown
                print(f"[STATS] Calculated from equity curve: CAGR={cagr:.4f}, Sharpe={sharpe_ratio:.4f}, Volatility={volatility:.4f}")
        
        # Extract with fallback chain: tradeStatistics > statistics > runtimeStatistics > calculated
        extracted = {
            # Core metrics - prefer tradeStatistics, fall back to runtime
            "total_return": self._parse_pct(runtime.get("Return", stats.get("Net Profit", "0%"))),
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            
            # Trade counts - use calculated trade_count
            "total_trades": trade_count,
            "winning_trades": winning_trades_final,
            "losing_trades": losing_trades_final,
            
            # Win rate
            "win_rate": win_rate,
            
            # Profit metrics - use calculated if tradeStatistics is empty
            "profit_factor": profit_factor,
            "avg_win": self._parse_currency(trade_stats.get("averageProfit", stats.get("Average Win", "0"))) if trade_stats else (total_profit / winning_trades if winning_trades > 0 else 0),
            "avg_loss": self._parse_currency(trade_stats.get("averageLoss", stats.get("Average Loss", "0"))) if trade_stats else (total_loss / losing_trades if losing_trades > 0 else 0),
            "largest_win": self._parse_currency(trade_stats.get("largestProfit", "0")) if trade_stats else largest_win,
            "largest_loss": self._parse_currency(trade_stats.get("largestLoss", "0")) if trade_stats else largest_loss,
            "total_profit": self._parse_currency(trade_stats.get("totalProfit", "0")) if trade_stats else total_profit,
            "total_loss": self._parse_currency(trade_stats.get("totalLoss", "0")) if trade_stats else total_loss,
            
            # Equity from runtimeStatistics
            "equity_final": self._parse_currency(runtime.get("Equity", stats.get("End Equity", "0"))),
            "equity_start": self._parse_currency(stats.get("Start Equity", "0")),
            "net_profit": self._parse_currency(runtime.get("Net Profit", "0")),
            
            # Additional metrics
            "cagr": cagr,
            "volatility": volatility,
            "max_drawdown_duration": trade_stats.get("maximumDrawdownDuration", "00:00:00") if trade_stats else "00:00:00",
            "calmar_ratio": calmar_ratio,
        }
        
        # Debug output
        print(f"[STATS] Extracted statistics:")
        for key, value in extracted.items():
            if value != 0 and value != "00:00:00":
                print(f"  {key}: {value}")
        
        return extracted
    
    def _extract_trades(self, results: Dict) -> List[Dict]:
        """
        Extract individual trades from LEAN results.
        
        These populate the Trades table for:
        - sp_GetLastTrades (Trade-Mind MCP)
        - sp_CalculateWinRate (Trade-Mind MCP)
        """
        trades_list = []
        
        # LEAN uses lowercase keys in newer versions
        # profitLoss contains timestamp -> P&L value (for long backtests)
        profit_loss = results.get("profitLoss", results.get("ProfitLoss", {}))
        
        for key, data in profit_loss.items():
            if isinstance(data, dict):
                # Old format: symbol -> {Net Profit, Quantity}
                trades_list.append({
                    "symbol": key,
                    "realized_pnl": data.get("Net Profit", data.get("net_profit", 0)),
                    "quantity": data.get("Quantity", data.get("quantity", 0)),
                })
            elif isinstance(data, (int, float)):
                # New format: timestamp -> P&L value (for long backtests)
                trades_list.append({
                    "symbol": "TQQQ",  # Default symbol for aggregated P&L
                    "realized_pnl": float(data),
                    "quantity": 0,
                    "time": key,
                })
        
        return trades_list
    
    def _extract_orders(self, results: Dict) -> List[Dict]:
        """Extract order history from LEAN results.
        
        Handles both uppercase (old LEAN) and lowercase (new LEAN) keys.
        """
        # LEAN uses lowercase keys in newer versions
        orders = results.get("orders", results.get("Orders", {}))
        orders_list = []
        
        for order_id, order_data in orders.items():
            # Handle both uppercase and lowercase symbol structure
            symbol_data = order_data.get("symbol", order_data.get("Symbol"))
            # symbol_data can be a dict {value, id, permtick} or None
            if isinstance(symbol_data, dict):
                symbol_value = symbol_data.get("value", symbol_data.get("Value", ""))
            elif symbol_data is not None:
                symbol_value = str(symbol_data)
            else:
                symbol_value = ""
            
            orders_list.append({
                "order_id": order_id,
                "symbol": symbol_value,
                "type": order_data.get("type", order_data.get("Type", "")),
                "status": order_data.get("status", order_data.get("Status", "")),
                "quantity": order_data.get("quantity", order_data.get("Quantity", 0)),
                "price": order_data.get("price", order_data.get("Price", 0)),
                "time": order_data.get("time", order_data.get("Time", "")),
            })
        
        return orders_list
    
    def _calculate_metrics_from_equity_curve(self, charts: Dict) -> Dict[str, float]:
        """
        Calculate performance metrics from the equity curve when LEAN doesn't provide them.
        
        For long backtests, LEAN may not populate statistics/totalPerformance, so we need
        to calculate CAGR, Sharpe, Sortino, and Volatility from the Strategy Equity chart.
        """
        import math
        
        # Get Strategy Equity chart
        strategy_chart = charts.get("Strategy Equity", charts.get("strategy equity", {}))
        if not strategy_chart:
            return {}
        
        series = strategy_chart.get("series", strategy_chart.get("Series", {}))
        equity_series = series.get("Equity", series.get("equity", {}))
        if not equity_series:
            return {}
        
        values = equity_series.get("values", equity_series.get("Values", []))
        if not values or len(values) < 2:
            return {}
        
        # Extract equity values (format: [timestamp, open, high, low, close] or [timestamp, value])
        equity_values = []
        timestamps = []
        for v in values:
            if isinstance(v, list) and len(v) >= 2:
                timestamps.append(v[0])
                # Use close price if OHLC, otherwise use the single value
                equity_values.append(v[-1] if len(v) >= 5 else v[1])
        
        if len(equity_values) < 2:
            return {}
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(equity_values)):
            if equity_values[i-1] > 0:
                daily_return = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
                daily_returns.append(daily_return)
        
        if not daily_returns:
            return {}
        
        # Calculate metrics
        initial_equity = equity_values[0]
        final_equity = equity_values[-1]
        
        # Calculate number of years from timestamps
        start_ts = timestamps[0]
        end_ts = timestamps[-1]
        years = (end_ts - start_ts) / (365.25 * 24 * 3600)  # Convert seconds to years
        
        if years <= 0:
            years = len(equity_values) / 252  # Assume ~252 trading days per year
        
        # CAGR (Compound Annual Growth Rate)
        if initial_equity > 0 and years > 0:
            cagr = (final_equity / initial_equity) ** (1 / years) - 1
        else:
            cagr = 0
        
        # Annualized Volatility (standard deviation of daily returns * sqrt(252))
        if len(daily_returns) > 1:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            daily_volatility = math.sqrt(variance)
            annual_volatility = daily_volatility * math.sqrt(252)
        else:
            annual_volatility = 0
        
        # Sharpe Ratio (assuming risk-free rate of 0 for simplicity)
        if annual_volatility > 0:
            sharpe_ratio = cagr / annual_volatility
        else:
            sharpe_ratio = 0
        
        # Sortino Ratio (using downside deviation)
        downside_returns = [r for r in daily_returns if r < 0]
        if len(downside_returns) > 1:
            downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_deviation = math.sqrt(downside_variance) * math.sqrt(252)
            sortino_ratio = cagr / downside_deviation if downside_deviation > 0 else 0
        else:
            sortino_ratio = sharpe_ratio  # Fall back to Sharpe if no downside returns
        
        print(f"[EQUITY CALC] Years: {years:.2f}, Initial: ${initial_equity:,.2f}, Final: ${final_equity:,.2f}")
        print(f"[EQUITY CALC] Daily returns count: {len(daily_returns)}, Downside returns count: {len(downside_returns)}")
        
        return {
            "cagr": cagr,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "volatility": annual_volatility,
        }
    
    def _parse_pct(self, value: str) -> float:
        """Parse percentage string to float."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("%", "").replace(",", "").replace("$", "")) / 100
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_number(self, value) -> float:
        """Parse number that might be string."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").replace("$", "").replace("%", ""))
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_int(self, value) -> int:
        """Parse integer that might be string."""
        if isinstance(value, int):
            return value
        try:
            return int(float(str(value).replace(",", "")))
        except (ValueError, AttributeError):
            return 0
    
    def _parse_currency(self, value) -> float:
        """Parse currency string like '$75,000.00' to float."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("$", "").replace(",", ""))
        except (ValueError, AttributeError):
            return 0.0
    
    # ============================================
    # SQL STORAGE (Trade-Mind MCP Data Source)
    # ============================================
    
    def store_results_in_sql(self, parsed_results: Dict) -> bool:
        """
        Store backtest results in SQL Server.
        
        This is the KEY INTEGRATION POINT for Trade-Mind MCP:
        - Populates BacktestOutcomes → for comparison queries
        - Populates Trades → for sp_GetLastTrades, sp_CalculateWinRate
        - Populates Sessions → for tracking
        """
        if not self.conn:
            print("[SQL] No database connection, skipping SQL storage")
            return False
        
        cursor = self.conn.cursor()
        session_id = parsed_results["session_id"]
        stats = parsed_results["statistics"]
        trades = parsed_results.get("trades", [])
        
        start_time = datetime.now()
        
        try:
            # 1. Create or update Session record
            print(f"[SQL] Creating/updating session record: {session_id}")
            
            # Get config data from parsed results
            initial_cash = parsed_results.get("initial_cash", 0)
            params_json = json.dumps(parsed_results.get("parameters", {}))
            
            # Check if session exists
            cursor.execute("SELECT 1 FROM Sessions WHERE SessionId = ?", (session_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                cursor.execute("""
                    UPDATE Sessions SET
                        Status = 'COMPLETED',
                        EndTime = GETUTCDATE(),
                        TotalReturn = ?, SharpeRatio = ?, MaxDrawdown = ?, 
                        TotalTrades = ?, WinRate = ?, ParametersJson = ?
                    WHERE SessionId = ?
                """, (
                    stats.get("total_return", 0),
                    stats.get("sharpe_ratio", 0),
                    stats.get("max_drawdown", 0),
                    stats.get("total_trades", 0),
                    stats.get("win_rate", 0),
                    params_json,
                    session_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO Sessions (
                        SessionId, SessionType, StrategyId, StartTime, EndTime, Status,
                        TotalReturn, SharpeRatio, MaxDrawdown, TotalTrades, WinRate, ParametersJson
                    ) VALUES (?, 'BACKTEST', 'TQQQ_SCALPING', GETUTCDATE(), GETUTCDATE(), 'COMPLETED',
                        ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    stats.get("total_return", 0),
                    stats.get("sharpe_ratio", 0),
                    stats.get("max_drawdown", 0),
                    stats.get("total_trades", 0),
                    stats.get("win_rate", 0),
                    params_json
                ))
            
            # 2. Store BacktestOutcome (for sp_SuggestCorrections)
            print(f"[SQL] Creating backtest outcome record")
            cursor.execute("""
                INSERT INTO BacktestOutcomes (
                    BacktestId, StrategyId, StartDate, EndDate, TotalReturn, SharpeRatio,
                    SortinoRatio, CAGR, MaxDrawdown, Volatility, TotalTrades, WinRate, 
                    ProfitFactor, WinningTrades, LosingTrades, TotalProfit, TotalLoss,
                    AverageWin, AverageLoss, LargestWin, LargestLoss, CalmarRatio,
                    ParametersJson
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                'TQQQ_SCALPING',
                parsed_results.get("start_date", datetime.now() - timedelta(days=365)),
                parsed_results.get("end_date", datetime.now()),
                stats.get("total_return", 0),
                stats.get("sharpe_ratio", 0),
                stats.get("sortino_ratio", 0),
                stats.get("cagr", 0),
                stats.get("max_drawdown", 0),
                stats.get("volatility", 0),
                stats.get("total_trades", 0),
                stats.get("win_rate", 0),
                stats.get("profit_factor", 0),
                stats.get("winning_trades", 0),
                stats.get("losing_trades", 0),
                stats.get("total_profit", 0),
                stats.get("total_loss", 0),
                stats.get("avg_win", 0),
                abs(stats.get("avg_loss", 0)),  # Store as positive value
                stats.get("largest_win", 0),
                abs(stats.get("largest_loss", 0)),  # Store as positive value
                stats.get("calmar_ratio", 0),
                json.dumps(parsed_results.get("parameters", {}))
            ))
            
            # 3. Store BacktestRuns (for History UI)
            print(f"[SQL] Creating backtest run record")
            cursor.execute("""
                INSERT INTO BacktestRuns (
                    RunID, StartTime, EndTime, Status, AlgorithmName,
                    BacktestStartDate, BacktestEndDate, InitialCapital
                ) VALUES (?, GETUTCDATE(), GETUTCDATE(), 'COMPLETED', 'TQQQScalpingAlgorithm', ?, ?, ?)
            """, (
                session_id,
                parsed_results.get("start_date"),
                parsed_results.get("end_date"),
                parsed_results.get("initial_cash", 100000)
            ))
            
            # 4. Store BacktestMetrics (individual metrics for detailed analysis)
            print(f"[SQL] Creating backtest metrics")
            metrics_to_store = [
                # Core performance
                ("TotalReturn", stats.get("total_return", 0)),
                ("SharpeRatio", stats.get("sharpe_ratio", 0)),
                ("SortinoRatio", stats.get("sortino_ratio", 0)),
                ("MaxDrawdown", stats.get("max_drawdown", 0)),
                ("CAGR", stats.get("cagr", 0)),
                ("Volatility", stats.get("volatility", 0)),
                ("CalmarRatio", stats.get("calmar_ratio", 0)),
                
                # Trade counts
                ("TotalTrades", stats.get("total_trades", 0)),
                ("WinningTrades", stats.get("winning_trades", 0)),
                ("LosingTrades", stats.get("losing_trades", 0)),
                ("WinRate", stats.get("win_rate", 0)),
                ("ProfitFactor", stats.get("profit_factor", 0)),
                
                # P&L metrics
                ("AvgWin", stats.get("avg_win", 0)),
                ("AvgLoss", abs(stats.get("avg_loss", 0))),
                ("LargestWin", stats.get("largest_win", 0)),
                ("LargestLoss", abs(stats.get("largest_loss", 0))),
                ("TotalProfit", stats.get("total_profit", 0)),
                ("TotalLoss", abs(stats.get("total_loss", 0))),
                ("NetProfit", stats.get("net_profit", 0)),
                
                # Equity
                ("EquityFinal", stats.get("equity_final", 0)),
                ("EquityStart", stats.get("equity_start", 0)),
            ]
            for metric_name, metric_value in metrics_to_store:
                cursor.execute("""
                    INSERT INTO BacktestMetrics (RunID, MetricName, MetricValue)
                    VALUES (?, ?, ?)
                """, (session_id, metric_name, metric_value))
            
            # 5. Store individual trades using BULK INSERT pattern (for Trade-Mind queries)
            # Use batch inserts instead of one-by-one to dramatically speed up large datasets
            # Trades table schema requires: Symbol, Direction, EntryTime, EntryPrice, EntryQuantity (NOT NULL)
            # SQL Server limit: 2100 parameters per query. With 8 params/trade, max batch = 250
            if trades:
                print(f"[SQL] Bulk inserting {len(trades)} trades...")
                batch_size = 250  # 250 * 8 = 2000 params (under SQL Server's 2100 limit)
                
                # Use current time as default for backtest trades (LEAN doesn't provide entry/exit times in profitLoss)
                default_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                for i in range(0, len(trades), batch_size):
                    batch = trades[i:i+batch_size]
                    
                    # Build multi-row insert matching actual Trades table schema
                    values_list = []
                    params_list = []
                    for j, trade in enumerate(batch):
                        # 8 parameters per trade
                        values_list.append("(?, ?, ?, ?, ?, ?, ?, ?)")
                        pnl = trade.get("realized_pnl", 0)
                        params_list.extend([
                            session_id,                           # SessionId
                            trade.get("symbol", "TQQQ"),          # Symbol
                            "LONG" if pnl >= 0 else "SHORT",      # Direction (infer from P&L)
                            trade.get("time", default_time),      # EntryTime
                            0.0,                                  # EntryPrice (not available from LEAN profitLoss)
                            abs(trade.get("quantity", 1)),        # EntryQuantity
                            pnl,                                  # NetPnL
                            "BACKTEST"                            # ExitReason
                        ])
                    
                    values_sql = ", ".join(values_list)
                    sql = f"""
                        INSERT INTO Trades (SessionId, Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, NetPnL, ExitReason)
                        VALUES {values_sql}
                    """
                    
                    cursor.execute(sql, params_list)
                    print(f"[SQL] Inserted batch {i//batch_size + 1} ({len(batch)} trades)")
            
            self.conn.commit()
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"[SQL] Stored results for session: {session_id} (took {elapsed:.1f}s)")
            return True
            
        except Exception as e:
            print(f"[SQL] Error storing results: {e}")
            self.conn.rollback()
            return False
    
    def save_results_to_file(self, parsed_results: Dict, config: BacktestConfig):
        """Save parsed results to JSON file for backup/debugging."""
        results_dir = self.results_path / config.session_id
        output_file = results_dir / "parsed_results.json"
        
        # Add config to results for full context
        output = {
            "config": asdict(config),
            "results": parsed_results,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"[FILE] Saved parsed results: {output_file}")
    
    # ============================================
    # MAIN EXECUTION
    # ============================================
    
    def run_backtest(
        self,
        start_date: str = "2024-01-01",
        end_date: str = "2024-12-31",
        initial_cash: float = 100000.0,
        session_id: str = None,
        **params
    ) -> Dict[str, Any]:
        """
        Run a single backtest and store results.
        
        Returns parsed results dict that can be used by Trade-Mind MCP.
        """
        # Use provided session ID or generate new one
        if session_id is None:
            session_id = self.generate_session_id()
        
        total_start = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"[BACKTEST] Session: {session_id}")
        print(f"[BACKTEST] Period: {start_date} to {end_date}")
        print(f"[BACKTEST] Initial Cash: ${initial_cash:,.2f}")
        if params:
            print(f"[BACKTEST] Parameters: {params}")
        print(f"{'='*60}\n")
        
        # Create config
        config = BacktestConfig(
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            **params
        )
        
        # Create LEAN config file
        step_start = datetime.now()
        config_path = self.create_lean_config(config)
        elapsed = (datetime.now() - step_start).total_seconds()
        print(f"[TIMING] Config creation: {elapsed:.1f}s")
        
        # Run LEAN backtest
        step_start = datetime.now()
        lean_result = self.run_lean_backtest(config_path)
        elapsed = (datetime.now() - step_start).total_seconds()
        print(f"[TIMING] LEAN execution: {elapsed:.1f}s")
        
        if not lean_result.get("success"):
            return {"success": False, "error": lean_result.get("error")}
        
        # Parse results (for Trade-Mind MCP)
        step_start = datetime.now()
        print(f"[PARSE] Parsing results for session: {session_id}")
        parsed_results = self.parse_backtest_results(session_id)
        
        # Add config data to parsed results for SQL storage
        parsed_results["start_date"] = start_date
        parsed_results["end_date"] = end_date
        parsed_results["initial_cash"] = initial_cash
        parsed_results["parameters"] = params
        
        elapsed = (datetime.now() - step_start).total_seconds()
        print(f"[TIMING] Results parsing: {elapsed:.1f}s")
        
        # Store in SQL (Trade-Mind data source)
        step_start = datetime.now()
        print(f"[SQL] Connecting to database...")
        self.connect_db()
        print(f"[SQL] Storing results...")
        self.store_results_in_sql(parsed_results)
        print(f"[SQL] Storage completed")
        elapsed = (datetime.now() - step_start).total_seconds()
        print(f"[TIMING] SQL storage: {elapsed:.1f}s")
        
        # Save to file (backup)
        step_start = datetime.now()
        print(f"[DEBUG] Starting file save...")
        self.save_results_to_file(parsed_results, config)
        print(f"[DEBUG] File save completed")
        elapsed = (datetime.now() - step_start).total_seconds()
        print(f"[TIMING] File save: {elapsed:.1f}s")
        
        total_elapsed = (datetime.now() - total_start).total_seconds()
        print(f"\n[TIMING] Total execution: {total_elapsed:.1f}s")
        print(f"[COMPLETE] Results stored for Trade-Mind MCP queries")
        print(f"[COMPLETE] Session ID: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "statistics": parsed_results.get("statistics", {}),
            "trade_count": len(parsed_results.get("trades", []))
        }


# ============================================
# PARAMETER SWEEP (For Optimization)
# ============================================

class ParameterSweeper:
    """
    Run multiple backtests with different parameters.
    
    Results are stored in SQL for Trade-Mind MCP analysis:
    - ParameterPerformance table
    - OptimalParameters table (after analysis)
    """
    
    def __init__(self, runner: BacktestRunner):
        self.runner = runner
    
    def sweep(
        self,
        param_name: str,
        values: List[Any],
        base_start: str = "2024-01-01",
        base_end: str = "2024-12-31"
    ) -> List[Dict]:
        """Run backtests sweeping one parameter."""
        results = []
        
        print(f"\n{'='*60}")
        print(f"[SWEEP] Parameter: {param_name}")
        print(f"[SWEEP] Values: {values}")
        print(f"{'='*60}\n")
        
        for value in values:
            params = {param_name.replace("-", "_"): value}
            result = self.runner.run_backtest(
                start_date=base_start,
                end_date=base_end,
                **params
            )
            
            if result.get("success"):
                result["param_name"] = param_name
                result["param_value"] = value
                results.append(result)
                
                # Store parameter performance in SQL
                self._store_param_performance(
                    param_name, str(value), result.get("statistics", {})
                )
        
        return results
    
    def _store_param_performance(
        self,
        param_name: str,
        param_value: str,
        stats: Dict
    ):
        """Store parameter performance for Trade-Mind analysis."""
        if not self.runner.conn:
            return
        
        cursor = self.runner.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO ParameterPerformance (
                    ParamName, ParamValue, MarketRegime,
                    TradeCount, WinRate, AvgPnLWhenUsed, SharpeRatio, MaxDrawdown
                ) VALUES (?, ?, 'ALL', ?, ?, ?, ?, ?)
            """, (
                param_name,
                param_value,
                stats.get("total_trades", 0),
                stats.get("win_rate", 0),
                stats.get("avg_win", 0) - abs(stats.get("avg_loss", 0)),
                stats.get("sharpe_ratio", 0),
                stats.get("max_drawdown", 0)
            ))
            self.runner.conn.commit()
        except Exception as e:
            print(f"[SQL] Error storing param performance: {e}")


# ============================================
# CLI ENTRY POINT
# ============================================

def main():
    parser = argparse.ArgumentParser(description="TQQQ Backtest Runner")
    parser.add_argument("--start", default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--cash", type=float, default=100000, help="Initial cash")
    parser.add_argument("--session-id", default=None, help="Session ID for this backtest")
    
    # Strategy parameters
    parser.add_argument("--rsi-period", type=int, default=14, help="RSI period")
    parser.add_argument("--rsi-oversold", type=float, default=30.0, help="RSI oversold threshold")
    parser.add_argument("--rsi-overbought", type=float, default=70.0, help="RSI overbought threshold")
    parser.add_argument("--bb-period", type=int, default=20, help="Bollinger Bands period")
    parser.add_argument("--bb-std-dev", type=float, default=2.0, help="Bollinger Bands std dev")
    parser.add_argument("--stop-loss", type=float, default=0.02, help="Stop loss percentage")
    parser.add_argument("--take-profit", type=float, default=0.03, help="Take profit percentage")
    
    # Sweep mode
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    parser.add_argument("--sweep-param", default="rsi_oversold", help="Parameter to sweep")
    parser.add_argument("--sweep-values", default="25,28,30,32,35", help="Comma-separated values")
    
    args = parser.parse_args()
    
    runner = BacktestRunner()
    
    if args.sweep:
        # Parameter sweep mode
        values = [float(v) if '.' in v else int(v) for v in args.sweep_values.split(",")]
        sweeper = ParameterSweeper(runner)
        results = sweeper.sweep(
            param_name=args.sweep_param,
            values=values,
            base_start=args.start,
            base_end=args.end
        )
        
        # Print summary
        print("\n" + "="*60)
        print("PARAMETER SWEEP RESULTS")
        print("="*60)
        for r in results:
            stats = r.get("statistics", {})
            print(f"{r['param_name']}={r['param_value']}: "
                  f"Return={stats.get('total_return', 0)*100:.2f}% "
                  f"Sharpe={stats.get('sharpe_ratio', 0):.2f} "
                  f"WinRate={stats.get('win_rate', 0)*100:.1f}%")
    else:
        # Single backtest mode
        # Build session ID from args or generate new one
        session_id = args.session_id if args.session_id else runner.generate_session_id()
        
        result = runner.run_backtest(
            start_date=args.start,
            end_date=args.end,
            initial_cash=args.cash,
            rsi_period=args.rsi_period,
            rsi_oversold=args.rsi_oversold,
            rsi_overbought=args.rsi_overbought,
            bb_period=args.bb_period,
            bb_std_dev=args.bb_std_dev,
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit,
            session_id=session_id
        )
        
        if result.get("success"):
            stats = result.get("statistics", {})
            print("\n" + "="*60)
            print("BACKTEST COMPLETE")
            print("="*60)
            print(f"Session ID: {result['session_id']}")
            print(f"Total Return: {stats.get('total_return', 0)*100:.2f}%")
            print(f"Sharpe Ratio: {stats.get('sharpe_ratio', 0):.2f}")
            print(f"Max Drawdown: {stats.get('max_drawdown', 0)*100:.2f}%")
            print(f"Win Rate: {stats.get('win_rate', 0)*100:.1f}%")
            print(f"Total Trades: {stats.get('total_trades', 0)}")
            print("\n[INFO] Results stored in SQL - available via Trade-Mind MCP")
        else:
            print("\n" + "="*60)
            print("BACKTEST FAILED")
            print("="*60)
            print(f"Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()

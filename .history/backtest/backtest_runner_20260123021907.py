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
    
    # Strategy parameters (can be overridden for sweeps)
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    bb_period: int = 20
    bb_std_dev: float = 2.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.03
    
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
        algo_files = ["TQQQScalpingAlgorithm.py", "sql_connector.py"]
        
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
        lean_config = {
            "environment": "backtesting",
            "algorithm-type-name": "TQQQScalpingAlgorithm",
            "algorithm-language": "Python",
            "algorithm-location": str(self.lean_path / "Algorithm.Python" / "TQQQScalpingAlgorithm.py"),
            "data-folder": str(self.lean_path / "Data"),
            
            # Parameters passed to algorithm
            "parameters": {
                "start-date": config.start_date,
                "end-date": config.end_date,
                "cash": str(config.initial_cash),
                "rsi-period": str(config.rsi_period),
                "rsi-oversold": str(config.rsi_oversold),
                "rsi-overbought": str(config.rsi_overbought),
                "bb-period": str(config.bb_period),
                "bb-std-dev": str(config.bb_std_dev),
                "stop-loss-pct": str(config.stop_loss_pct),
                "take-profit-pct": str(config.take_profit_pct),
                "session-id": config.session_id,
                # Webhook simulation (enabled by default for backtests)
                "webhook-simulation": "true",
                "webhook-log-path": str(self.results_path / config.session_id / "webhook_log.txt")
            },
            
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
            
            # Run LEAN with our config
            result = subprocess.run(
                [str(launcher_path), f"--config={config_path}"],
                cwd=str(self.lean_path / "Launcher"),
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout for longer backtests
                env=env
            )
            
            # Check for success - ignore the GIL error on shutdown which is cosmetic
            output_combined = (result.stdout or "") + (result.stderr or "")
            
            # Success indicators from LEAN output
            backtest_completed = "Engine.Main(): Analysis Complete" in output_combined or \
                                 "ALGORITHM COMPLETED" in output_combined or \
                                 "STATISTICS::" in output_combined
            
            if backtest_completed:
                print("[LEAN] Backtest completed successfully")
                # The GIL error at shutdown is harmless - ignore it
                return {"success": True, "stdout": result.stdout}
            elif result.returncode != 0 and not backtest_completed:
                print(f"[LEAN] Error: {result.stderr}")
                return {"success": False, "error": result.stderr}
            else:
                print("[LEAN] Backtest completed")
                return {"success": True, "stdout": result.stdout}
            
        except subprocess.TimeoutExpired:
            print("[LEAN] Backtest timed out")
            return {"success": False, "error": "Timeout"}
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
        
        # Find the results JSON file (LEAN creates this)
        results_file = None
        for f in results_dir.glob("*.json"):
            if f.name != "config.json":
                results_file = f
                break
        
        if not results_file:
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
        """Extract performance statistics from LEAN results."""
        stats = results.get("Statistics", {})
        runtime = results.get("RuntimeStatistics", {})
        
        return {
            "total_return": self._parse_pct(stats.get("Total Net Profit", "0%")),
            "sharpe_ratio": float(stats.get("Sharpe Ratio", 0)),
            "max_drawdown": self._parse_pct(stats.get("Drawdown", "0%")),
            "total_trades": int(stats.get("Total Trades", 0)),
            "win_rate": self._parse_pct(stats.get("Win Rate", "0%")),
            "profit_factor": float(stats.get("Profit-Loss Ratio", 0)),
            "avg_win": float(stats.get("Average Win", 0)),
            "avg_loss": float(stats.get("Average Loss", 0)),
            "equity_final": float(runtime.get("Equity", "0").replace("$", "").replace(",", "")),
        }
    
    def _extract_trades(self, results: Dict) -> List[Dict]:
        """
        Extract individual trades from LEAN results.
        
        These populate the Trades table for:
        - sp_GetLastTrades (Trade-Mind MCP)
        - sp_CalculateWinRate (Trade-Mind MCP)
        """
        trades_list = []
        
        # LEAN stores trades in different formats depending on version
        # Check for TradeStatistics or ProfitLoss sections
        profit_loss = results.get("ProfitLoss", {})
        
        for symbol, data in profit_loss.items():
            if isinstance(data, dict):
                trades_list.append({
                    "symbol": symbol,
                    "realized_pnl": data.get("Net Profit", 0),
                    "quantity": data.get("Quantity", 0),
                })
        
        return trades_list
    
    def _extract_orders(self, results: Dict) -> List[Dict]:
        """Extract order history from LEAN results."""
        orders = results.get("Orders", {})
        orders_list = []
        
        for order_id, order_data in orders.items():
            orders_list.append({
                "order_id": order_id,
                "symbol": order_data.get("Symbol", {}).get("Value", ""),
                "type": order_data.get("Type", ""),
                "status": order_data.get("Status", ""),
                "quantity": order_data.get("Quantity", 0),
                "price": order_data.get("Price", 0),
                "time": order_data.get("Time", ""),
            })
        
        return orders_list
    
    def _parse_pct(self, value: str) -> float:
        """Parse percentage string to float."""
        if isinstance(value, (int, float)):
            return float(value)
        return float(value.replace("%", "").replace(",", "")) / 100
    
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
            # 1. Create Session record
            print(f"[SQL] Creating session record: {session_id}")
            cursor.execute("""
                INSERT INTO Sessions (
                    SessionId, SessionType, StrategyId, StartTime, Status,
                    TotalReturn, SharpeRatio, MaxDrawdown, TotalTrades, WinRate
                ) VALUES (?, 'BACKTEST', 'TQQQ_SCALPING', GETUTCDATE(), 'COMPLETED',
                    ?, ?, ?, ?, ?)
            """, (
                session_id,
                stats.get("total_return", 0),
                stats.get("sharpe_ratio", 0),
                stats.get("max_drawdown", 0),
                stats.get("total_trades", 0),
                stats.get("win_rate", 0)
            ))
            
            # 2. Store BacktestOutcome (for sp_SuggestCorrections)
            print(f"[SQL] Creating backtest outcome record")
            cursor.execute("""
                INSERT INTO BacktestOutcomes (
                    SessionId, BacktestStart, BacktestEnd, TotalReturn, SharpeRatio,
                    MaxDrawdown, TotalTrades, WinRate, ProfitFactor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                datetime.now() - timedelta(days=365),  # Placeholder dates
                datetime.now(),
                stats.get("total_return", 0),
                stats.get("sharpe_ratio", 0),
                stats.get("max_drawdown", 0),
                stats.get("total_trades", 0),
                stats.get("win_rate", 0),
                stats.get("profit_factor", 0)
            ))
            
            # 3. Store individual trades using BULK INSERT pattern (for Trade-Mind queries)
            # Use batch inserts instead of one-by-one to dramatically speed up large datasets
            if trades:
                print(f"[SQL] Bulk inserting {len(trades)} trades...")
                batch_size = 1000
                for i in range(0, len(trades), batch_size):
                    batch = trades[i:i+batch_size]
                    
                    # Build multi-row insert
                    values_list = []
                    params_list = []
                    for j, trade in enumerate(batch):
                        values_list.append(f"(?, ?, 'BUY', ?, ?)")
                        params_list.extend([
                            session_id,
                            trade.get("symbol", "TQQQ"),
                            trade.get("quantity", 0),
                            trade.get("realized_pnl", 0)
                        ])
                    
                    values_sql = ", ".join(values_list)
                    sql = f"""
                        INSERT INTO Trades (SessionId, Symbol, Side, Quantity, RealizedPnL)
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
        print(f"[DEBUG] Starting results parsing for session: {session_id}")
        parsed_results = self.parse_backtest_results(session_id)
        print(f"[DEBUG] Results parsing completed")
        elapsed = (datetime.now() - step_start).total_seconds()
        print(f"[TIMING] Results parsing: {elapsed:.1f}s")
        
        # Store in SQL (Trade-Mind data source)
        step_start = datetime.now()
        print(f"[DEBUG] Starting database connection...")
        self.connect_db()
        print(f"[DEBUG] Starting SQL storage...")
        self.store_results_in_sql(parsed_results)
        print(f"[DEBUG] SQL storage completed")
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

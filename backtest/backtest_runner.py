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
    
    def __init__(self, connection_string: str = None):
        self.base_path = Path(__file__).parent.parent
        self.lean_path = self.base_path / "quantconnect-lean"
        self.results_path = self.base_path / "backtest" / "results"
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        # SQL Connection (for Trade-Mind MCP data)
        self.conn_string = connection_string or self._get_default_connection_string()
        self.conn: Optional[pyodbc.Connection] = None
    
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
                "session-id": config.session_id
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
            # Run LEAN with our config
            result = subprocess.run(
                [str(launcher_path), f"--config={config_path}"],
                cwd=str(self.lean_path / "Launcher"),
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                print(f"[LEAN] Error: {result.stderr}")
                return {"success": False, "error": result.stderr}
            
            print("[LEAN] Backtest completed successfully")
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
        
        try:
            # 1. Create Session record
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
            
            # 3. Store individual trades (for Trade-Mind queries)
            for trade in parsed_results.get("trades", []):
                cursor.execute("""
                    INSERT INTO Trades (
                        SessionId, Symbol, Side, Quantity, RealizedPnL
                    ) VALUES (?, ?, 'BUY', ?, ?)
                """, (
                    session_id,
                    trade.get("symbol", "TQQQ"),
                    trade.get("quantity", 0),
                    trade.get("realized_pnl", 0)
                ))
            
            self.conn.commit()
            print(f"[SQL] Stored results for session: {session_id}")
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
        **params
    ) -> Dict[str, Any]:
        """
        Run a single backtest and store results.
        
        Returns parsed results dict that can be used by Trade-Mind MCP.
        """
        # Generate session ID
        session_id = self.generate_session_id()
        print(f"\n{'='*60}")
        print(f"[BACKTEST] Session: {session_id}")
        print(f"[BACKTEST] Period: {start_date} to {end_date}")
        print(f"[BACKTEST] Initial Cash: ${initial_cash:,.2f}")
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
        config_path = self.create_lean_config(config)
        
        # Run LEAN backtest
        lean_result = self.run_lean_backtest(config_path)
        
        if not lean_result.get("success"):
            return {"success": False, "error": lean_result.get("error")}
        
        # Parse results (for Trade-Mind MCP)
        parsed_results = self.parse_backtest_results(session_id)
        
        # Store in SQL (Trade-Mind data source)
        self.connect_db()
        self.store_results_in_sql(parsed_results)
        
        # Save to file (backup)
        self.save_results_to_file(parsed_results, config)
        
        print(f"\n[COMPLETE] Results stored for Trade-Mind MCP queries")
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
        result = runner.run_backtest(
            start_date=args.start,
            end_date=args.end,
            initial_cash=args.cash
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


if __name__ == "__main__":
    main()

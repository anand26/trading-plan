"""
Multi-ETF Mean Reversion (RSI) — Backtest Runner
===================================================
Independent backtest runner for the Multi-ETF RSI(2) Mean Reversion strategy.
Executes LEAN backtests across QQQ + SPY + IWM + DIA basket.

Usage:
    python multi_etf_meanrev_runner.py                                          # Single run, all 4 ETFs
    python multi_etf_meanrev_runner.py --symbols QQQ                           # Single ETF
    python multi_etf_meanrev_runner.py --symbols QQQ,SPY,IWM,DIA              # Full basket
    python multi_etf_meanrev_runner.py --start 2000-06-01 --end 2026-02-05     # Custom dates
    python multi_etf_meanrev_runner.py --csv multi_etf_sweep.csv               # Batch from CSV
"""

import os
import sys
import json
import uuid
import hashlib
import argparse
import subprocess
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ============================================
# CONFIGURATION
# ============================================

@dataclass
class MultiETFConfig:
    """Configuration for a Multi-ETF Mean Reversion backtest run."""
    session_id: str
    start_date: str
    end_date: str
    initial_cash: float = 100000.0
    
    # Algorithm
    algorithm_name: str = "MultiETFMeanReversionAlgorithm"
    
    # Symbols — comma-separated
    symbols: str = "QQQ,SPY,IWM,DIA"
    
    # RSI settings
    rsi_period: int = 2
    rsi_entry: float = 15.0
    rsi_exit: float = 90.0
    
    # Trend filter
    trend_sma: int = 200
    use_trend_filter: bool = True
    
    # Position sizing — total allocation across ALL positions
    allocation: float = 0.90
    
    # Max hold days (0 = unlimited)
    max_hold_days: int = 0
    
    # Data resolution
    data_resolution: str = "minute"


class MultiETFRunner:
    """
    Runs LEAN backtests for the Multi-ETF Mean Reversion strategy.
    """
    
    def __init__(self, connection_string: str | None = None):
        self.base_path = Path(__file__).parent.parent
        self.lean_path = self.base_path / "quantconnect-lean"
        self.results_path = self.base_path / "backtest" / "results"
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        self._sync_algorithm_files()
        
        self.conn_string = connection_string or self._get_default_connection_string()
        self.conn: Optional[Any] = None
    
    def _sync_algorithm_files(self) -> None:
        """Sync Multi-ETF algorithm to LEAN folder."""
        source_algo_dir = self.base_path / "algorithms"
        target_algo_dir = self.lean_path / "Algorithm.Python"
        
        algo_files = [
            "MultiETFMeanReversionAlgorithm.py",
            "sql_connector.py",
        ]
        
        for filename in algo_files:
            src = source_algo_dir / filename
            dst = target_algo_dir / filename
            if src.exists():
                shutil.copy2(src, dst)
                print(f"[SYNC] Copied {filename} to LEAN folder")
    
    def _get_default_connection_string(self) -> str:
        return (
            "Driver={ODBC Driver 17 for SQL Server};"
            "Server=localhost;"
            "Database=TradingDB;"
            "Trusted_Connection=yes;"
        )
    
    def connect_db(self) -> bool:
        if not HAS_PYODBC:
            print("[DB] pyodbc not available, skipping SQL storage")
            return False
        try:
            self.conn = pyodbc.connect(self.conn_string)
            print("[DB] Connected to TradingDB")
            return True
        except Exception as e:
            print(f"[DB] Connection failed: {e}")
            return False
    
    def generate_session_id(self, prefix: str = "METF") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{short_uuid}"
    
    # ============================================
    # LEAN CONFIG GENERATION
    # ============================================
    
    def create_lean_config(self, config: MultiETFConfig) -> Path:
        """Create LEAN config file for Multi-ETF backtest."""
        
        parameters = {
            "start-date": config.start_date,
            "end-date": config.end_date,
            "cash": str(config.initial_cash),
            
            # Symbols
            "symbols": config.symbols,
            
            # RSI settings
            "rsi-period": str(config.rsi_period),
            "rsi-entry": str(config.rsi_entry),
            "rsi-exit": str(config.rsi_exit),
            
            # Trend filter
            "trend-sma": str(config.trend_sma),
            "use-trend-filter": str(config.use_trend_filter).lower(),
            
            # Position sizing
            "allocation": str(config.allocation),
            
            # Max hold
            "max-hold-days": str(config.max_hold_days),
            
            # Data resolution
            "data-resolution": config.data_resolution,
            
            # Session tracking
            "session-id": config.session_id,
        }
        
        algo_name = config.algorithm_name
        algo_file = f"{algo_name}.py"
        
        lean_config = {
            "environment": "backtesting",
            "algorithm-type-name": algo_name,
            "algorithm-language": "Python",
            "algorithm-location": str(self.lean_path / "Algorithm.Python" / algo_file),
            "data-folder": str(self.lean_path / "Data"),
            "parameters": parameters,
            "results-destination-folder": str(self.results_path / config.session_id),
            "transaction-log": str(self.results_path / config.session_id / "transactions.csv"),
            "live-mode": False,
            "setup-handler": "QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler",
            "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler",
            "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
            "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",
            "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
        }
        
        session_results_path = self.results_path / config.session_id
        session_results_path.mkdir(parents=True, exist_ok=True)
        
        config_path = session_results_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump(lean_config, f, indent=2)
        
        print(f"[CONFIG] Created: {config_path}")
        return config_path
    
    # ============================================
    # LEAN EXECUTION
    # ============================================
    
    def run_lean_backtest(self, config_path: Path, algo_name: str = "MultiETFMeanReversionAlgorithm") -> Dict[str, Any]:
        """Execute LEAN backtest and return results."""
        launcher_path = self.lean_path / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.exe"
        
        if not launcher_path.exists():
            launcher_path = self.lean_path / "Launcher" / "bin" / "Release" / "QuantConnect.Lean.Launcher.exe"
        
        if not launcher_path.exists():
            print("[LEAN] Launcher not found! Build LEAN first with build_lean.ps1")
            return {"success": False, "error": "LEAN launcher not found"}
        
        print(f"[LEAN] Running Multi-ETF Mean Reversion backtest...")
        
        try:
            env = os.environ.copy()
            
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
                    env["PYTHONNET_PYDLL"] = dll_path
                    env["PYTHONHOME"] = home
                    env["PYTHONPATH"] = os.path.join(home, "Lib") + ";" + os.path.join(home, "DLLs")
                    env["PATH"] = home + ";" + env.get("PATH", "")
                    print(f"[LEAN] Using Python: {home}")
                    break
            
            # LEAN names the result file after the algorithm class name
            result_file = self.results_path / config_path.parent.name / f"{algo_name}.json"
            
            process = subprocess.Popen(
                [str(launcher_path), f"--config", str(config_path)],
                cwd=str(self.lean_path / "Launcher" / "bin" / "Debug"),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            max_wait_time = 900  # 15 min — multi-symbol takes longer
            poll_interval = 5
            waited = 0
            
            print(f"[LEAN] Monitoring for completion...")
            
            while waited < max_wait_time:
                if process.poll() is not None:
                    print(f"[LEAN] Process exited with code: {process.returncode}")
                    break
                
                if result_file.exists() and result_file.stat().st_size > 1000:
                    json_complete = False
                    try:
                        with open(result_file, 'r') as rf:
                            result_data = json.load(rf)
                        state = result_data.get('state', {})
                        has_total_perf = bool(result_data.get('totalPerformance'))
                        status = state.get('Status', '')
                        if has_total_perf or status == 'Completed':
                            json_complete = True
                    except (json.JSONDecodeError, IOError):
                        pass
                    
                    if json_complete:
                        print(f"[LEAN] Results fully written - backtest complete")
                        time.sleep(3)
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=2)
                        break
                    
                    if process.poll() is not None:
                        print(f"[LEAN] Process exited (code {process.returncode}), accepting results")
                        break
                
                time.sleep(poll_interval)
                waited += poll_interval
                if waited % 30 == 0:
                    print(f"[LEAN] Still running... ({waited}s elapsed)")
            
            backtest_completed = result_file.exists() and result_file.stat().st_size > 1000
            
            if backtest_completed:
                print("[LEAN] Multi-ETF backtest completed successfully")
                return {"success": True}
            elif waited >= max_wait_time:
                print("[LEAN] Timeout!")
                if process.poll() is None:
                    process.kill()
                return {"success": False, "error": "Timeout"}
            else:
                return {"success": False, "error": "LEAN exited without results"}
            
        except Exception as e:
            print(f"[LEAN] Execution error: {e}")
            return {"success": False, "error": str(e)}
    
    # ============================================
    # RESULTS PARSING
    # ============================================
    
    def parse_backtest_results(self, session_id: str) -> Dict[str, Any]:
        """Parse LEAN backtest output files."""
        results_dir = self.results_path / session_id
        
        results_file = None
        for f in results_dir.glob("*.json"):
            if f.name not in ["config.json"] and "data-monitor" not in f.name \
               and not f.name.endswith("-summary.json") and not f.name.endswith("-order-events.json") \
               and f.name != "parsed_results.json":
                results_file = f
                break
        
        if not results_file or not results_file.exists():
            print(f"[PARSE] No results file found in {results_dir}")
            return {}
        
        with open(results_file, 'r') as f:
            lean_results = json.load(f)
        
        parsed = {
            "session_id": session_id,
            "statistics": self._extract_statistics(lean_results),
            "trades": self._extract_trades(lean_results),
            "orders": self._extract_orders(lean_results),
        }
        return parsed
    
    def _extract_statistics(self, results: Dict) -> Dict[str, float]:
        """Extract performance statistics from LEAN results."""
        stats = results.get("statistics", results.get("Statistics", {}))
        runtime = results.get("runtimeStatistics", results.get("RuntimeStatistics", {}))
        total_perf = results.get("totalPerformance", {}) or {}
        trade_stats = (total_perf.get("tradeStatistics", {}) or {})
        
        return {
            "total_return": self._parse_pct(runtime.get("Return", stats.get("Net Profit", "0%"))),
            "sharpe_ratio": self._parse_number(trade_stats.get("sharpeRatio", stats.get("Sharpe Ratio", 0))),
            "sortino_ratio": self._parse_number(trade_stats.get("sortinoRatio", stats.get("Sortino Ratio", 0))),
            "max_drawdown": self._parse_pct(stats.get("Drawdown", "0%")),
            "total_trades": self._parse_int(trade_stats.get("totalNumberOfTrades", stats.get("Total Orders", 0))),
            "winning_trades": self._parse_int(trade_stats.get("numberOfWinningTrades", 0)),
            "losing_trades": self._parse_int(trade_stats.get("numberOfLosingTrades", 0)),
            "win_rate": self._parse_number(trade_stats.get("winRate", 0)) if trade_stats.get("winRate") else self._parse_pct(stats.get("Win Rate", "0%")),
            "profit_factor": self._parse_number(trade_stats.get("profitFactor", stats.get("Profit-Loss Ratio", 0))),
            "avg_win": self._parse_currency(trade_stats.get("averageProfit", stats.get("Average Win", "0"))),
            "avg_loss": self._parse_currency(trade_stats.get("averageLoss", stats.get("Average Loss", "0"))),
            "total_profit": self._parse_currency(trade_stats.get("totalProfit", "0")),
            "total_loss": self._parse_currency(trade_stats.get("totalLoss", "0")),
            "equity_final": self._parse_currency(runtime.get("Equity", "0")),
            "net_profit": self._parse_currency(runtime.get("Net Profit", "0")),
            "cagr": self._parse_pct(stats.get("Compounding Annual Return", "0%")),
            "volatility": self._parse_pct(stats.get("Annual Standard Deviation", "0%")),
            "calmar_ratio": self._parse_number(trade_stats.get("profitToMaxDrawdownRatio", 0)),
            "largest_win": self._parse_currency(trade_stats.get("largestProfit", "0")),
            "largest_loss": self._parse_currency(trade_stats.get("largestLoss", "0")),
        }
    
    def _extract_trades(self, results: Dict) -> List[Dict]:
        trades_list = []
        profit_loss = results.get("ProfitLoss", {})
        for symbol, data in profit_loss.items():
            if isinstance(data, dict):
                trades_list.append({"symbol": symbol, "realized_pnl": data.get("Net Profit", 0)})
        return trades_list
    
    def _extract_orders(self, results: Dict) -> List[Dict]:
        orders = results.get("Orders", {})
        return [
            {
                "order_id": oid,
                "symbol": od.get("Symbol", {}).get("Value", ""),
                "type": od.get("Type", ""),
                "status": od.get("Status", ""),
                "quantity": od.get("Quantity", 0),
                "price": od.get("Price", 0),
                "time": od.get("Time", ""),
            }
            for oid, od in orders.items()
        ]
    
    def _parse_pct(self, value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("%", "").replace(",", "").replace("$", "")) / 100
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_number(self, value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").replace("$", "").replace("%", ""))
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_int(self, value) -> int:
        if isinstance(value, int):
            return value
        try:
            return int(float(str(value).replace(",", "")))
        except (ValueError, AttributeError):
            return 0
    
    def _parse_currency(self, value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("$", "").replace(",", ""))
        except (ValueError, AttributeError):
            return 0.0
    
    # ============================================
    # SQL STORAGE
    # ============================================
    
    def store_results_in_sql(self, parsed_results: Dict) -> bool:
        if not self.conn:
            return False
        
        cursor = self.conn.cursor()
        session_id = parsed_results["session_id"]
        stats = parsed_results["statistics"]
        
        try:
            params_json = json.dumps(parsed_results.get("parameters", {}))
            
            # Session table
            cursor.execute("SELECT 1 FROM Sessions WHERE SessionId = ?", (session_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                cursor.execute("""
                    UPDATE Sessions SET
                        Status = 'COMPLETED', EndTime = GETUTCDATE(),
                        TotalReturn = ?, SharpeRatio = ?, MaxDrawdown = ?, 
                        TotalTrades = ?, WinRate = ?, ParametersJson = ?
                    WHERE SessionId = ?
                """, (
                    stats.get("total_return", 0), stats.get("sharpe_ratio", 0),
                    stats.get("max_drawdown", 0), stats.get("total_trades", 0),
                    stats.get("win_rate", 0), params_json, session_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO Sessions (
                        SessionId, SessionType, StrategyId, StartTime, EndTime, Status,
                        TotalReturn, SharpeRatio, MaxDrawdown, TotalTrades, WinRate, ParametersJson
                    ) VALUES (?, 'BACKTEST', 'MULTI_ETF_MEAN_REVERSION', GETUTCDATE(), GETUTCDATE(), 'COMPLETED',
                        ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, stats.get("total_return", 0), stats.get("sharpe_ratio", 0),
                    stats.get("max_drawdown", 0), stats.get("total_trades", 0),
                    stats.get("win_rate", 0), params_json
                ))
            
            # BacktestOutcome
            win_rate = stats.get("win_rate", 0)
            avg_win = stats.get("avg_win", 0)
            avg_loss = abs(stats.get("avg_loss", 0))
            sharpe = stats.get("sharpe_ratio", 0)
            max_dd = stats.get("max_drawdown", 0)
            total_trades = stats.get("total_trades", 0)
            
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if total_trades > 0 else 0
            expectancy_ratio = expectancy / avg_loss if avg_loss > 0 else 0
            
            if sharpe >= 2.0:
                grade = 'A'
            elif sharpe >= 1.5:
                grade = 'B+'
            elif sharpe >= 1.0:
                grade = 'B'
            elif sharpe >= 0.5:
                grade = 'C+'
            elif sharpe >= 0:
                grade = 'C'
            else:
                grade = 'D'
            
            is_successful = 1 if (sharpe >= 1.0 and win_rate >= 0.4 and abs(max_dd) <= 0.20) else 0
            
            notes_parts = []
            if stats.get("total_return", 0) > 0:
                notes_parts.append(f"Profitable ({stats.get('total_return', 0)*100:.1f}%)")
            else:
                notes_parts.append(f"Loss ({stats.get('total_return', 0)*100:.1f}%)")
            notes_parts.append(f"Grade:{grade}")
            symbols_str = parsed_results.get("parameters", {}).get("symbols", "QQQ,SPY,IWM,DIA")
            notes_parts.append(f"Symbols:{symbols_str}")
            if total_trades == 0:
                notes_parts.append("NO TRADES")
            notes = " | ".join(notes_parts)
            
            optimization_run_id = parsed_results.get("optimization_run_id")
            exec_time = parsed_results.get("execution_time_seconds", 0)
            
            cursor.execute("""
                INSERT INTO BacktestOutcomes (
                    BacktestId, StrategyId, StartDate, EndDate, TotalReturn, SharpeRatio,
                    SortinoRatio, CAGR, MaxDrawdown, Volatility, TotalTrades, WinRate, 
                    ProfitFactor, WinningTrades, LosingTrades, TotalProfit, TotalLoss,
                    AverageWin, AverageLoss, LargestWin, LargestLoss, CalmarRatio,
                    Expectancy, ExpectancyRatio, PerformanceGrade, IsSuccessful,
                    ExecutionTimeSeconds, Notes, OptimizationRunId, ParametersJson
                ) VALUES (?, 'MULTI_ETF_MEAN_REVERSION', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                parsed_results.get("start_date"), parsed_results.get("end_date"),
                stats.get("total_return", 0), stats.get("sharpe_ratio", 0),
                stats.get("sortino_ratio", 0), stats.get("cagr", 0),
                stats.get("max_drawdown", 0), stats.get("volatility", 0),
                stats.get("total_trades", 0), stats.get("win_rate", 0),
                stats.get("profit_factor", 0), stats.get("winning_trades", 0),
                stats.get("losing_trades", 0), stats.get("total_profit", 0),
                abs(stats.get("total_loss", 0)), stats.get("avg_win", 0),
                abs(stats.get("avg_loss", 0)),
                stats.get("largest_win", 0), abs(stats.get("largest_loss", 0)),
                stats.get("calmar_ratio", 0),
                expectancy, expectancy_ratio, grade, is_successful,
                exec_time, notes, optimization_run_id,
                json.dumps(parsed_results.get("parameters", {}))
            ))
            
            self.conn.commit()
            print(f"[SQL] Stored Multi-ETF results: {session_id}")
            return True
            
        except Exception as e:
            print(f"[SQL] Error: {e}")
            self.conn.rollback()
            return False
    
    def save_results_to_file(self, parsed_results: Dict, config: MultiETFConfig):
        results_dir = self.results_path / config.session_id
        output_file = results_dir / "parsed_results.json"
        output = {
            "config": asdict(config),
            "results": parsed_results,
            "timestamp": datetime.now().isoformat()
        }
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        print(f"[FILE] Saved: {output_file}")
    
    # ============================================
    # MAIN EXECUTION
    # ============================================
    
    def run_backtest(
        self,
        start_date: str = "2000-06-01",
        end_date: str = "2026-02-05",
        initial_cash: float = 100000.0,
        session_id: str = None,
        **params
    ) -> Dict[str, Any]:
        """Run a single Multi-ETF Mean Reversion backtest."""
        if session_id is None:
            session_id = self.generate_session_id()
        
        total_start = datetime.now()
        
        optimization_run_id = params.pop('_optimization_run_id', None)
        
        symbols_display = params.get('symbols', 'QQQ,SPY,IWM,DIA')
        
        print(f"\n{'='*60}")
        print(f"[MULTI-ETF BACKTEST] Session: {session_id}")
        print(f"[MULTI-ETF BACKTEST] Symbols: {symbols_display}")
        print(f"[MULTI-ETF BACKTEST] Period: {start_date} to {end_date}")
        print(f"[MULTI-ETF BACKTEST] Cash: ${initial_cash:,.2f}")
        if params:
            print(f"[MULTI-ETF BACKTEST] Params: {params}")
        print(f"{'='*60}\n")
        
        config = MultiETFConfig(
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            **params
        )
        
        config_path = self.create_lean_config(config)
        lean_result = self.run_lean_backtest(config_path, algo_name=config.algorithm_name)
        
        if not lean_result.get("success"):
            return {"success": False, "error": lean_result.get("error")}
        
        parsed_results = self.parse_backtest_results(session_id)
        parsed_results["start_date"] = start_date
        parsed_results["end_date"] = end_date
        parsed_results["initial_cash"] = initial_cash
        parsed_results["parameters"] = params
        parsed_results["optimization_run_id"] = optimization_run_id
        parsed_results["execution_time_seconds"] = int((datetime.now() - total_start).total_seconds())
        
        self.connect_db()
        self.store_results_in_sql(parsed_results)
        self.save_results_to_file(parsed_results, config)
        
        total_elapsed = parsed_results["execution_time_seconds"]
        print(f"[COMPLETE] Multi-ETF backtest done in {total_elapsed:.1f}s | Session: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "statistics": parsed_results.get("statistics", {}),
        }


# ============================================
# CSV-DRIVEN BATCH OPTIMIZER
# ============================================

class MultiETFOptimizer:
    """
    CSV-driven batch optimizer for Multi-ETF Mean Reversion.
    Resume-capable with hash-based deduplication.
    """
    
    PARAM_COLUMNS = [
        'symbols',
        'rsi_period', 'rsi_entry', 'rsi_exit',
        'trend_sma', 'use_trend_filter',
        'allocation',
        'max_hold_days',
        'data_resolution',
    ]
    
    DEFAULTS = {
        'algorithm_name': 'MultiETFMeanReversionAlgorithm',
        'symbols': 'QQQ,SPY,IWM,DIA',
        'rsi_period': 2,
        'rsi_entry': 15,
        'rsi_exit': 90,
        'trend_sma': 200,
        'use_trend_filter': True,
        'allocation': 0.90,
        'max_hold_days': 0,
        'data_resolution': 'minute',
    }
    
    def __init__(self, connection_string: str = None):
        self.runner = MultiETFRunner(connection_string)
        self.base_path = Path(__file__).parent
        self._completed_hashes: set = set()
    
    @staticmethod
    def generate_hash(params: Dict[str, Any]) -> str:
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:12]
    
    def load_combinations_from_csv(
        self, file_path: str,
        start_date: str = None, end_date: str = None,
        initial_cash: float = None
    ) -> List[Dict[str, Any]]:
        """Load parameter combinations from CSV."""
        if not HAS_PANDAS:
            raise ImportError("pandas required: pip install pandas")
        
        df = pd.read_csv(file_path)
        print(f"[CSV] Loaded {len(df)} combinations from {Path(file_path).name}")
        
        combinations = []
        for idx, row in df.iterrows():
            params = {}
            for col in self.PARAM_COLUMNS:
                if col in row and pd.notna(row[col]):
                    val = row[col]
                    if col == 'use_trend_filter':
                        val = str(val).lower() in ('true', '1', 'yes')
                    params[col] = val
                elif col in self.DEFAULTS:
                    params[col] = self.DEFAULTS[col]
            
            params['algorithm_name'] = 'MultiETFMeanReversionAlgorithm'
            csv_start = row.get('start_date', None)
            csv_end = row.get('end_date', None)
            csv_cash = row.get('initial_cash', None)
            params['start_date'] = start_date or (csv_start if pd.notna(csv_start) else None) or "2000-06-01"
            params['end_date'] = end_date or (csv_end if pd.notna(csv_end) else None) or "2026-02-05"
            params['initial_cash'] = initial_cash or (csv_cash if pd.notna(csv_cash) else None) or 100000.0
            
            params = {k: v for k, v in params.items() if not (isinstance(v, float) and v != v)}
            params['_hash'] = self.generate_hash(params)
            params['_row_index'] = idx + 1
            
            combinations.append(params)
        
        # Deduplicate
        seen = set()
        unique = []
        for combo in combinations:
            h = combo['_hash']
            if h not in seen:
                seen.add(h)
                unique.append(combo)
        
        print(f"[CSV] {len(unique)} unique combinations")
        return unique
    
    def _load_completed_hashes(self):
        if not self.runner.conn:
            self.runner.connect_db()
        if not self.runner.conn:
            return
        try:
            cursor = self.runner.conn.cursor()
            cursor.execute("""
                SELECT BacktestId FROM BacktestOutcomes
                WHERE StrategyId = 'MULTI_ETF_MEAN_REVERSION'
            """)
            rows = cursor.fetchall()
            self._completed_hashes = set()
            for row in rows:
                self._completed_hashes.add(row[0])
            print(f"[BATCH] {len(self._completed_hashes)} previously completed runs found")
        except Exception as e:
            print(f"[BATCH] Warning: Could not load completed hashes: {e}")
    
    def run_batch_optimization(
        self,
        combinations: List[Dict[str, Any]],
        results_csv: str = "multi_etf_results.csv",
        source_csv: str = None,
    ):
        """Run all parameter combinations with resume support."""
        self._load_completed_hashes()
        
        run_id = f"METF_OPT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._create_optimization_run(run_id, len(combinations), source_csv)
        
        completed = 0
        failed = 0
        
        for i, combo in enumerate(combinations, 1):
            combo_hash = combo.get('_hash', '')
            row_idx = combo.get('_row_index', i)
            
            print(f"\n[BATCH] Running {i}/{len(combinations)} (hash: {combo_hash})")
            
            run_params = {k: v for k, v in combo.items()
                         if k not in ('start_date', 'end_date', 'initial_cash', '_hash', '_row_index')}
            run_params['_optimization_run_id'] = run_id
            
            try:
                result = self.runner.run_backtest(
                    start_date=combo.get('start_date', '2000-06-01'),
                    end_date=combo.get('end_date', '2026-02-05'),
                    initial_cash=combo.get('initial_cash', 100000.0),
                    **run_params
                )
                
                if result.get("success"):
                    result['_hash'] = combo_hash
                    result['parameters'] = run_params
                    self._append_result_to_csv(result, results_csv)
                    completed += 1
                else:
                    print(f"[ERROR] Combination {row_idx} failed: {result.get('error')}")
                    failed += 1
                    
            except Exception as e:
                print(f"[ERROR] Combination {row_idx} failed: {e}")
                failed += 1
            
            self._update_optimization_run(run_id, completed, "RUNNING")
        
        self._update_optimization_run(run_id, completed, "COMPLETED")
        
        print(f"\n{'='*60}")
        print(f"[BATCH COMPLETE] {completed} succeeded, {failed} failed out of {len(combinations)}")
        print(f"[BATCH COMPLETE] Results saved to: {results_csv}")
        print(f"{'='*60}")
    
    def _create_optimization_run(self, run_id: str, total_combinations: int, source_file: str = None):
        if not self.runner.conn:
            self.runner.connect_db()
        if not self.runner.conn:
            return
        try:
            cursor = self.runner.conn.cursor()
            cursor.execute("""
                INSERT INTO OptimizationRuns (RunId, StartTime, TotalCombinations, CompletedCombinations, Status, SourceFile)
                VALUES (?, GETUTCDATE(), ?, 0, 'RUNNING', ?)
            """, (run_id, total_combinations, source_file))
            self.runner.conn.commit()
            print(f"[SQL] OptimizationRuns: Created {run_id} ({total_combinations} combos)")
        except Exception as e:
            print(f"[SQL] Error inserting optimization run: {e}")
    
    def _update_optimization_run(self, run_id: str, completed_count: int, status: str):
        if not self.runner.conn:
            return
        try:
            cursor = self.runner.conn.cursor()
            cursor.execute("""
                UPDATE OptimizationRuns
                SET CompletedCombinations = ?, Status = ?,
                    EndTime = CASE WHEN ? = 'COMPLETED' THEN GETUTCDATE() ELSE EndTime END
                WHERE RunId = ?
            """, (completed_count, status, status, run_id))
            self.runner.conn.commit()
        except Exception as e:
            print(f"[SQL] Error updating optimization run: {e}")
    
    def _append_result_to_csv(self, result: Dict, csv_path: str):
        stats = result.get("statistics", {})
        params = result.get("parameters", {})
        
        row = {
            "session_id": result.get("session_id", ""),
            "hash": result.get("_hash", ""),
            "symbols": params.get("symbols", "QQQ,SPY,IWM,DIA"),
            "rsi_period": params.get("rsi_period", 2),
            "rsi_entry": params.get("rsi_entry", 15),
            "rsi_exit": params.get("rsi_exit", 90),
            "trend_sma": params.get("trend_sma", 200),
            "use_trend_filter": params.get("use_trend_filter", True),
            "allocation": params.get("allocation", 0.90),
            "max_hold_days": params.get("max_hold_days", 0),
            "TotalReturn": stats.get("total_return", 0),
            "SharpeRatio": stats.get("sharpe_ratio", 0),
            "MaxDrawdown": stats.get("max_drawdown", 0),
            "WinRate": stats.get("win_rate", 0),
            "TotalTrades": stats.get("total_trades", 0),
            "ProfitFactor": stats.get("profit_factor", 0),
            "CAGR": stats.get("cagr", 0),
            "AvgWin": stats.get("avg_win", 0),
            "AvgLoss": stats.get("avg_loss", 0),
            "CalmarRatio": stats.get("calmar_ratio", 0),
            "ParametersJson": json.dumps(params),
        }
        
        csv_file = Path(csv_path) if os.path.isabs(csv_path) else Path.cwd() / csv_path
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        write_header = not csv_file.exists()
        
        if HAS_PANDAS:
            df = pd.DataFrame([row])
            df.to_csv(csv_file, mode='a', header=write_header, index=False)
        else:
            import csv
            with open(csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if write_header:
                    writer.writeheader()
                writer.writerow(row)


# ============================================
# CLI ENTRY POINT
# ============================================

def main():
    parser = argparse.ArgumentParser(description="Multi-ETF Mean Reversion Backtest Runner")
    
    # Date range
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--cash", type=float, default=100000, help="Initial cash")
    parser.add_argument("--session-id", default=None)
    
    # Symbols
    parser.add_argument("--symbols", default="QQQ,SPY,IWM,DIA",
                        help="Comma-separated symbols (default: QQQ,SPY,IWM,DIA)")
    
    # RSI parameters
    parser.add_argument("--rsi-period", type=int, default=2)
    parser.add_argument("--rsi-entry", type=float, default=15)
    parser.add_argument("--rsi-exit", type=float, default=90)
    
    # Trend filter
    parser.add_argument("--trend-sma", type=int, default=200)
    parser.add_argument("--use-trend-filter", action="store_true", default=True)
    parser.add_argument("--no-trend-filter", dest="use_trend_filter", action="store_false")
    
    # Position sizing
    parser.add_argument("--allocation", type=float, default=0.90)
    
    # Max hold
    parser.add_argument("--max-hold-days", type=int, default=0)
    
    # Data resolution
    parser.add_argument("--data-resolution", default="minute", choices=["daily", "minute"])
    
    # Batch mode
    parser.add_argument("--csv", default=None, help="CSV file for batch optimization")
    parser.add_argument("--results-csv", default="multi_etf_results.csv", help="Output results CSV")
    
    args = parser.parse_args()
    
    if args.csv:
        # Batch mode
        optimizer = MultiETFOptimizer()
        combinations = optimizer.load_combinations_from_csv(
            args.csv, start_date=args.start, end_date=args.end, initial_cash=args.cash
        )
        optimizer.run_batch_optimization(combinations, args.results_csv, source_csv=args.csv)
    else:
        # Single run
        runner = MultiETFRunner()
        result = runner.run_backtest(
            start_date=args.start or "2000-06-01",
            end_date=args.end or "2026-02-05",
            initial_cash=args.cash,
            session_id=args.session_id,
            symbols=args.symbols,
            rsi_period=args.rsi_period,
            rsi_entry=args.rsi_entry,
            rsi_exit=args.rsi_exit,
            trend_sma=args.trend_sma,
            use_trend_filter=args.use_trend_filter,
            allocation=args.allocation,
            max_hold_days=args.max_hold_days,
            data_resolution=args.data_resolution,
        )
        
        if result.get("success"):
            stats = result.get("statistics", {})
            print(f"\n{'='*60}")
            print(f"MULTI-ETF MEAN REVERSION BACKTEST COMPLETE")
            print(f"{'='*60}")
            print(f"Session: {result['session_id']}")
            print(f"Symbols: {args.symbols}")
            print(f"Return:  {stats.get('total_return', 0)*100:.2f}%")
            print(f"Sharpe:  {stats.get('sharpe_ratio', 0):.2f}")
            print(f"MaxDD:   {stats.get('max_drawdown', 0)*100:.2f}%")
            print(f"Win%:    {stats.get('win_rate', 0)*100:.1f}%")
            print(f"Trades:  {stats.get('total_trades', 0)}")
            print(f"CAGR:    {stats.get('cagr', 0)*100:.2f}%")
            print(f"PF:      {stats.get('profit_factor', 0):.2f}")
        else:
            print(f"\nFAILED: {result.get('error')}")


if __name__ == "__main__":
    main()

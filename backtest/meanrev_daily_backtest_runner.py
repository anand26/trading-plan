"""
TQQQ/SQQQ Daily Mean Reversion - Backtest Runner
==================================================
Independent backtest runner for the Daily Mean Reversion strategy.
Executes LEAN backtests, parses results, stores in SQL.

Usage:
    python meanrev_daily_backtest_runner.py                           # Single run with defaults
    python meanrev_daily_backtest_runner.py --start 2018-06-01 --end 2026-01-14
    python meanrev_daily_backtest_runner.py --csv parameter_combinations_meanrev_v1.0.csv

This runner is INDEPENDENT from the Turtle and pairs strategy runners.
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
class DailyMRBacktestConfig:
    """Configuration for a Daily Mean Reversion backtest run."""
    session_id: str
    start_date: str
    end_date: str
    initial_cash: float = 100000.0
    
    # Strategy identifier
    algorithm_name: str = "TQQQDailyMeanReversionAlgorithm"
    
    # ==========================================
    # DAILY MEAN REVERSION PARAMETERS
    # ==========================================
    
    # Z-score settings (daily bars)
    zscore_lookback: int = 30        # 30 trading days
    entry_zscore: float = 2.0        # Enter when |Z| > 2.0
    exit_target_zscore: float = 0.0  # Exit at full reversion (Z → 0)
    
    # Risk management
    stop_loss_pct: float = 0.05      # 5% stop for multi-day holds
    
    # Position sizing
    position_size: float = 0.50      # 50% of portfolio
    
    # Hold time
    max_hold_days: int = 20          # Max 20 days
    min_days_between: int = 1        # Min 1 day between trades
    
    # Trailing stop
    trailing_stop_atr: float = 0.0   # 0 = disabled
    atr_period: int = 14
    
    # RSI filter
    use_rsi_filter: bool = False
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    
    # Volatility scaling
    use_vol_scaling: bool = False
    vol_scale_threshold: float = 1.5
    vol_scale_factor: float = 0.5


class DailyMRBacktestRunner:
    """
    Runs LEAN backtests for the Daily Mean Reversion strategy.
    Independent from all other strategy runners.
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
        """Sync Daily Mean Reversion algorithm to LEAN folder"""
        source_algo_dir = self.base_path / "algorithms"
        target_algo_dir = self.lean_path / "Algorithm.Python"
        
        algo_files = [
            "TQQQDailyMeanReversionAlgorithm.py",
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
            print("[DB] pyodbc not available")
            return False
        try:
            self.conn = pyodbc.connect(self.conn_string)
            print("[DB] Connected to TradingDB")
            return True
        except Exception as e:
            print(f"[DB] Connection failed: {e}")
            return False
    
    def generate_session_id(self, prefix: str = "DAILYMR") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{short_uuid}"
    
    # ============================================
    # LEAN CONFIG GENERATION
    # ============================================
    
    def create_lean_config(self, config: DailyMRBacktestConfig) -> Path:
        """Create LEAN config file for Daily Mean Reversion backtest."""
        
        parameters = {
            "start-date": config.start_date,
            "end-date": config.end_date,
            "cash": str(config.initial_cash),
            
            # Z-score
            "zscore-lookback": str(config.zscore_lookback),
            "entry-zscore": str(config.entry_zscore),
            "exit-target-zscore": str(config.exit_target_zscore),
            
            # Risk
            "stop-loss-pct": str(config.stop_loss_pct),
            
            # Position sizing
            "position-size": str(config.position_size),
            
            # Hold time
            "max-hold-days": str(config.max_hold_days),
            "min-days-between": str(config.min_days_between),
            
            # Trailing stop
            "trailing-stop-atr": str(config.trailing_stop_atr),
            "atr-period": str(config.atr_period),
            
            # RSI filter
            "use-rsi-filter": str(config.use_rsi_filter).lower(),
            "rsi-period": str(config.rsi_period),
            "rsi-oversold": str(config.rsi_oversold),
            "rsi-overbought": str(config.rsi_overbought),
            
            # Vol scaling
            "use-vol-scaling": str(config.use_vol_scaling).lower(),
            "vol-scale-threshold": str(config.vol_scale_threshold),
            "vol-scale-factor": str(config.vol_scale_factor),
            
            # Session
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
    
    def run_lean_backtest(self, config_path: Path) -> Dict[str, Any]:
        """Execute LEAN backtest and return results."""
        launcher_path = self.lean_path / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.exe"
        if not launcher_path.exists():
            launcher_path = self.lean_path / "Launcher" / "bin" / "Release" / "QuantConnect.Lean.Launcher.exe"
        if not launcher_path.exists():
            return {"success": False, "error": "LEAN launcher not found"}
        
        print(f"[LEAN] Running DailyMR backtest with config: {config_path}")
        
        try:
            env = os.environ.copy()
            python_paths = [
                (r"C:\Users\anand\AppData\Local\Programs\Python\Python311", "python311.dll"),
                (r"C:\Users\anand\AppData\Local\Programs\Python\Python310", "python310.dll"),
                (r"C:\Users\anand\AppData\Local\Programs\Python\Python39", "python39.dll"),
                (r"C:\Python311", "python311.dll"),
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
            
            process = subprocess.Popen(
                [str(launcher_path), f"--config={config_path}"],
                cwd=str(self.lean_path / "Launcher"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            
            results_dir = Path(config_path).parent
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            algo_name = cfg.get('algorithm-type-name', 'TQQQDailyMeanReversionAlgorithm')
            result_file = results_dir / f"{algo_name}.json"
            log_file = results_dir / f"{algo_name}-log.txt"
            max_wait_time = 1800
            poll_interval = 2
            waited = 0
            
            print(f"[LEAN] Monitoring for completion...")
            
            while waited < max_wait_time:
                if process.poll() is not None:
                    break
                
                if result_file.exists() and result_file.stat().st_size > 1000:
                    log_complete = False
                    if log_file.exists():
                        try:
                            log_content = log_file.read_text(encoding='utf-8', errors='ignore')
                            if "Algorithm Id:" in log_content or "STATISTICS::" in log_content:
                                log_complete = True
                        except Exception:
                            pass
                    
                    if log_complete:
                        print(f"[LEAN] Results detected - backtest complete")
                        time.sleep(1)
                        if process.poll() is None:
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
                    print(f"[LEAN] Still running... ({waited}s)")
            
            if result_file.exists() and result_file.stat().st_size > 1000:
                print("[LEAN] DailyMR backtest completed successfully")
                return {"success": True}
            elif waited >= max_wait_time:
                if process.poll() is None:
                    process.kill()
                return {"success": False, "error": "Timeout"}
            else:
                return {"success": False, "error": "LEAN exited without results"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============================================
    # RESULTS PARSING
    # ============================================
    
    def parse_backtest_results(self, session_id: str) -> Dict[str, Any]:
        results_dir = self.results_path / session_id
        
        results_file = None
        for f in results_dir.glob("*.json"):
            if f.name not in ["config.json"] and "data-monitor" not in f.name \
               and not f.name.endswith("-summary.json") and not f.name.endswith("-order-events.json"):
                results_file = f
                break
        
        if not results_file or not results_file.exists():
            return {}
        
        with open(results_file, 'r') as f:
            lean_results = json.load(f)
        
        return {
            "session_id": session_id,
            "statistics": self._extract_statistics(lean_results),
            "trades": self._extract_trades(lean_results),
            "orders": self._extract_orders(lean_results),
        }
    
    def _extract_statistics(self, results: Dict) -> Dict[str, float]:
        stats = results.get("statistics", results.get("Statistics", {}))
        runtime = results.get("runtimeStatistics", results.get("RuntimeStatistics", {}))
        total_perf = results.get("totalPerformance", {})
        trade_stats = total_perf.get("tradeStatistics", {})
        
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
            "avg_win": self._parse_currency(trade_stats.get("averageProfit", "0")),
            "avg_loss": self._parse_currency(trade_stats.get("averageLoss", "0")),
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
                    ) VALUES (?, 'BACKTEST', 'DAILY_MEAN_REVERSION', GETUTCDATE(), GETUTCDATE(), 'COMPLETED',
                        ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, stats.get("total_return", 0), stats.get("sharpe_ratio", 0),
                    stats.get("max_drawdown", 0), stats.get("total_trades", 0),
                    stats.get("win_rate", 0), params_json
                ))
            
            # BacktestOutcome — compute derived metrics
            win_rate = stats.get("win_rate", 0)
            avg_win = stats.get("avg_win", 0)
            avg_loss = abs(stats.get("avg_loss", 0))
            sharpe = stats.get("sharpe_ratio", 0)
            max_dd = stats.get("max_drawdown", 0)
            total_trades = stats.get("total_trades", 0)
            
            # Expectancy = WR * AvgWin - (1-WR) * AvgLoss
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if total_trades > 0 else 0
            # ExpectancyRatio = Expectancy / AvgLoss (how many R per trade)
            expectancy_ratio = expectancy / avg_loss if avg_loss > 0 else 0
            
            # Performance Grade based on Sharpe
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
            
            # IsSuccessful: Sharpe >= 1.0, WR >= 40%, DD <= 20%
            is_successful = 1 if (sharpe >= 1.0 and win_rate >= 0.4 and abs(max_dd) <= 0.20) else 0
            
            # Auto-generate Notes
            notes_parts = []
            if stats.get("total_return", 0) > 0:
                notes_parts.append(f"Profitable ({stats.get('total_return', 0)*100:.1f}%)")
            else:
                notes_parts.append(f"Loss ({stats.get('total_return', 0)*100:.1f}%)")
            notes_parts.append(f"Grade:{grade}")
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
                ) VALUES (?, 'DAILY_MEAN_REVERSION', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            print(f"[SQL] Stored DailyMR results: {session_id}")
            return True
        except Exception as e:
            print(f"[SQL] Error: {e}")
            self.conn.rollback()
            return False
    
    def save_results_to_file(self, parsed_results: Dict, config: DailyMRBacktestConfig):
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
        start_date: str = "2018-06-01",
        end_date: str = "2026-01-14",
        initial_cash: float = 100000.0,
        session_id: str = None,
        **params
    ) -> Dict[str, Any]:
        """Run a single Daily Mean Reversion backtest."""
        if session_id is None:
            session_id = self.generate_session_id()
        
        total_start = datetime.now()
        
        # Extract optimization metadata (not a strategy param)
        optimization_run_id = params.pop('_optimization_run_id', None)
        
        print(f"\n{'='*60}")
        print(f"[DAILYMR BACKTEST] Session: {session_id}")
        print(f"[DAILYMR BACKTEST] Period: {start_date} to {end_date}")
        print(f"[DAILYMR BACKTEST] Cash: ${initial_cash:,.2f}")
        if params:
            print(f"[DAILYMR BACKTEST] Params: {params}")
        print(f"{'='*60}\n")
        
        config = DailyMRBacktestConfig(
            session_id=session_id,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            **params
        )
        
        config_path = self.create_lean_config(config)
        lean_result = self.run_lean_backtest(config_path)
        
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
        print(f"[COMPLETE] DailyMR backtest done in {total_elapsed:.1f}s | Session: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "statistics": parsed_results.get("statistics", {}),
        }


# ============================================
# CSV-DRIVEN BATCH OPTIMIZER
# ============================================

class DailyMRParameterOptimizer:
    """
    CSV-driven batch optimizer for Daily Mean Reversion parameters.
    """
    
    PARAM_COLUMNS = [
        'zscore_lookback', 'entry_zscore', 'exit_target_zscore',
        'stop_loss_pct', 'position_size',
        'max_hold_days', 'min_days_between',
        'trailing_stop_atr', 'atr_period',
        'use_rsi_filter', 'rsi_period', 'rsi_oversold', 'rsi_overbought',
        'use_vol_scaling', 'vol_scale_threshold', 'vol_scale_factor',
    ]
    
    DEFAULTS = {
        'algorithm_name': 'TQQQDailyMeanReversionAlgorithm',
        'zscore_lookback': 30,
        'entry_zscore': 2.0,
        'exit_target_zscore': 0.0,
        'stop_loss_pct': 0.05,
        'position_size': 0.50,
        'max_hold_days': 20,
        'min_days_between': 1,
        'trailing_stop_atr': 0.0,
        'atr_period': 14,
        'use_rsi_filter': False,
        'rsi_period': 14,
        'rsi_oversold': 30.0,
        'rsi_overbought': 70.0,
        'use_vol_scaling': False,
        'vol_scale_threshold': 1.5,
        'vol_scale_factor': 0.5,
    }
    
    def __init__(self, connection_string: str = None):
        self.runner = DailyMRBacktestRunner(connection_string)
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
                    if col in ('use_rsi_filter', 'use_vol_scaling'):
                        val = str(val).lower() in ('true', '1', 'yes')
                    params[col] = val
                elif col in self.DEFAULTS:
                    params[col] = self.DEFAULTS[col]
            
            params['algorithm_name'] = 'TQQQDailyMeanReversionAlgorithm'
            # Priority: CLI arg > CSV value > hardcoded default
            csv_start = row.get('start_date', None)
            csv_end = row.get('end_date', None)
            csv_cash = row.get('initial_cash', None)
            params['start_date'] = start_date or (csv_start if pd.notna(csv_start) else None) or "2018-06-01"
            params['end_date'] = end_date or (csv_end if pd.notna(csv_end) else None) or "2026-01-14"
            params['initial_cash'] = initial_cash or (csv_cash if pd.notna(csv_cash) else None) or 100000.0
            
            params = {k: v for k, v in params.items() if not (isinstance(v, float) and v != v)}
            params['_hash'] = self.generate_hash(params)
            params['_row_index'] = idx + 1
            
            combinations.append(params)
        
        seen = set()
        unique = []
        for c in combinations:
            if c['_hash'] not in seen:
                seen.add(c['_hash'])
                unique.append(c)
            else:
                print(f"[CSV] Skipping duplicate row {c['_row_index']}")
        
        print(f"[CSV] {len(unique)} unique combinations")
        return unique
    
    def _load_completed_hashes(self) -> set:
        completed = set()
        results_dir = self.base_path / "results"
        if results_dir.exists():
            for session_dir in results_dir.iterdir():
                if session_dir.is_dir() and session_dir.name.startswith("DAILYMR_"):
                    parsed_file = session_dir / "parsed_results.json"
                    if parsed_file.exists():
                        try:
                            with open(parsed_file) as f:
                                data = json.load(f)
                            params = data.get("config", {})
                            h = self.generate_hash(params)
                            completed.add(h)
                        except Exception:
                            pass
        return completed
    
    def run_batch_optimization(
        self, combinations: List[Dict[str, Any]],
        results_csv: str = "dailymr_optimization_results.csv",
        source_csv: str = None
    ) -> List[Dict[str, Any]]:
        """Run all combinations with resume support."""
        
        self._completed_hashes = self._load_completed_hashes()
        print(f"[BATCH] {len(self._completed_hashes)} previously completed")
        
        # Generate a unique optimization run ID for this batch
        optimization_run_id = f"OPT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[BATCH] Optimization Run ID: {optimization_run_id}")
        
        # Register optimization run in database
        self._insert_optimization_run(optimization_run_id, len(combinations), source_csv)
        
        results = []
        total = len(combinations)
        completed_count = 0
        
        for i, combo in enumerate(combinations, 1):
            combo_hash = combo.get('_hash', '')
            
            if combo_hash in self._completed_hashes:
                print(f"[SKIP] {i}/{total} - already done")
                continue
            
            print(f"\n[BATCH] Running {i}/{total} (hash: {combo_hash})")
            
            run_params = {k: v for k, v in combo.items() if not k.startswith('_') and k not in ('start_date', 'end_date', 'initial_cash')}
            run_params['_optimization_run_id'] = optimization_run_id
            
            try:
                result = self.runner.run_backtest(
                    start_date=combo.get('start_date', '2018-06-01'),
                    end_date=combo.get('end_date', '2026-01-14'),
                    initial_cash=combo.get('initial_cash', 100000.0),
                    **run_params
                )
                
                if result.get("success"):
                    result['_hash'] = combo_hash
                    result['_row'] = combo.get('_row_index', i)
                    result['parameters'] = run_params
                    results.append(result)
                    self._completed_hashes.add(combo_hash)
                    completed_count += 1
                    self._append_result_to_csv(result, results_csv)
                    
                    # Update progress in OptimizationRuns
                    self._update_optimization_run(optimization_run_id, completed_count, 'RUNNING')
                    
            except Exception as e:
                print(f"[ERROR] Combination {i} failed: {e}")
        
        # Mark optimization run as complete
        self._update_optimization_run(optimization_run_id, completed_count, 'COMPLETED')
        print(f"\n[BATCH] Complete: {len(results)}/{total} successful")
        return results
    
    def _insert_optimization_run(self, run_id: str, total_combinations: int, source_file: str = None):
        """Insert a new row into OptimizationRuns table."""
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
        """Update progress/status in OptimizationRuns table."""
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
            **params,
            "total_return": stats.get("total_return", 0),
            "sharpe_ratio": stats.get("sharpe_ratio", 0),
            "max_drawdown": stats.get("max_drawdown", 0),
            "win_rate": stats.get("win_rate", 0),
            "total_trades": stats.get("total_trades", 0),
            "profit_factor": stats.get("profit_factor", 0),
            "cagr": stats.get("cagr", 0),
            "avg_win": stats.get("avg_win", 0),
            "avg_loss": stats.get("avg_loss", 0),
            "calmar_ratio": stats.get("calmar_ratio", 0),
        }
        
        csv_file = self.base_path / csv_path
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
    parser = argparse.ArgumentParser(description="Daily Mean Reversion Backtest Runner")
    parser.add_argument("--start", default=None, help="Start date (YYYY-MM-DD, default: 2018-06-01)")
    parser.add_argument("--end", default=None, help="End date (YYYY-MM-DD, default: 2026-01-14)")
    parser.add_argument("--cash", type=float, default=100000, help="Initial cash")
    parser.add_argument("--session-id", default=None)
    
    # Strategy parameters
    parser.add_argument("--zscore-lookback", type=int, default=30)
    parser.add_argument("--entry-zscore", type=float, default=2.0)
    parser.add_argument("--exit-target-zscore", type=float, default=0.0)
    parser.add_argument("--stop-loss-pct", type=float, default=0.05)
    parser.add_argument("--position-size", type=float, default=0.50)
    parser.add_argument("--max-hold-days", type=int, default=20)
    parser.add_argument("--trailing-stop-atr", type=float, default=0.0)
    parser.add_argument("--use-rsi-filter", action="store_true")
    parser.add_argument("--use-vol-scaling", action="store_true")
    
    # Batch mode
    parser.add_argument("--csv", default=None, help="CSV file for batch optimization")
    parser.add_argument("--results-csv", default="dailymr_optimization_results.csv")
    
    args = parser.parse_args()
    
    if args.csv:
        optimizer = DailyMRParameterOptimizer()
        combinations = optimizer.load_combinations_from_csv(
            args.csv, start_date=args.start, end_date=args.end, initial_cash=args.cash
        )
        optimizer.run_batch_optimization(combinations, args.results_csv, source_csv=args.csv)
    else:
        runner = DailyMRBacktestRunner()
        result = runner.run_backtest(
            start_date=args.start or "2018-06-01",
            end_date=args.end or "2026-01-14",
            initial_cash=args.cash,
            session_id=args.session_id,
            zscore_lookback=args.zscore_lookback,
            entry_zscore=args.entry_zscore,
            exit_target_zscore=args.exit_target_zscore,
            stop_loss_pct=args.stop_loss_pct,
            position_size=args.position_size,
            max_hold_days=args.max_hold_days,
            trailing_stop_atr=args.trailing_stop_atr,
            use_rsi_filter=args.use_rsi_filter,
            use_vol_scaling=args.use_vol_scaling,
        )
        
        if result.get("success"):
            stats = result.get("statistics", {})
            print(f"\n{'='*60}")
            print(f"DAILY MEAN REVERSION BACKTEST COMPLETE")
            print(f"{'='*60}")
            print(f"Session: {result['session_id']}")
            print(f"Return:  {stats.get('total_return', 0)*100:.2f}%")
            print(f"Sharpe:  {stats.get('sharpe_ratio', 0):.2f}")
            print(f"MaxDD:   {stats.get('max_drawdown', 0)*100:.2f}%")
            print(f"Win%:    {stats.get('win_rate', 0)*100:.1f}%")
            print(f"Trades:  {stats.get('total_trades', 0)}")
            print(f"CAGR:    {stats.get('cagr', 0)*100:.2f}%")
        else:
            print(f"\nFAILED: {result.get('error')}")


if __name__ == "__main__":
    main()

"""
TQQQ/SQQQ Trading System - Parameter Optimizer
===============================================
Systematic parameter optimization for Trade-Mind MCP learning.

This module runs parameter sweeps and stores results in SQL,
enabling Trade-Mind MCP to:
1. Identify optimal parameters per market regime
2. Suggest corrections based on historical performance
3. Learn which parameter combinations work best

The optimizer populates:
- ParameterPerformance → per-parameter metrics
- OptimalParameters → best values per regime
- BacktestOutcomes → full backtest results

CSV-driven batch optimization:
- Load combinations from CSV/Excel
- Resume interrupted runs (skip completed)
- Track progress and store results for dashboard filtering
"""

import json
import hashlib
import itertools
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import pyodbc

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from backtest_runner import BacktestRunner, BacktestConfig


@dataclass
class ParameterRange:
    """Define a parameter and its sweep range."""
    name: str
    values: List[Any]
    param_type: str = "float"  # float, int, bool


@dataclass 
class SweepResult:
    """Result from a single parameter combination backtest."""
    params: Dict[str, Any]
    session_id: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_factor: float
    avg_trade_duration: float
    combination_hash: str = ""  # For deduplication and filtering


@dataclass
class OptimizationRun:
    """Tracks a batch optimization run."""
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_combinations: int = 0
    completed_combinations: int = 0
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    source_file: str = ""
    results: List[SweepResult] = field(default_factory=list)


class ParameterOptimizer:
    """
    Multi-parameter optimizer for strategy tuning.
    
    Supports:
    - Grid search (all combinations)
    - Single parameter sweeps
    - Market regime-specific optimization
    - CSV/Excel-driven batch optimization
    - Resume interrupted runs
    
    Results feed into Trade-Mind MCP for adaptive suggestions.
    """
    
    def __init__(self, connection_string: str = None):
        self.runner = BacktestRunner(connection_string)
        self.results: List[SweepResult] = []
        self.base_path = Path(__file__).parent
        self.current_run: Optional[OptimizationRun] = None
        self._completed_hashes: set = set()
    
    # ============================================
    # CSV/EXCEL INPUT HANDLING
    # ============================================
    
    @staticmethod
    def generate_combination_hash(params: Dict[str, Any]) -> str:
        """Generate a unique hash for a parameter combination."""
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()[:12]
    
    def load_combinations_from_csv(
        self,
        file_path: str,
        start_date: str = None,
        end_date: str = None,
        initial_cash: float = None
    ) -> List[Dict[str, Any]]:
        """
        Load parameter combinations from CSV or Excel file.
        
        Expected columns (all optional, uses defaults if missing):
        - rsi_period, rsi_oversold, rsi_overbought
        - bb_period, bb_std_dev
        - stop_loss_pct, take_profit_pct
        - ema_fast_period, ema_slow_period
        - start_date, end_date, initial_cash (optional per-row overrides)
        
        Returns list of parameter dictionaries ready for backtesting.
        """
        if not HAS_PANDAS:
            raise ImportError("pandas is required for CSV loading. Install with: pip install pandas")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Parameter file not found: {file_path}")
        
        # Load based on extension
        if file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        print(f"[CSV] Loaded {len(df)} combinations from {file_path.name}")
        
        # Get default values
        defaults = self._get_parameter_defaults()
        
        combinations = []
        for idx, row in df.iterrows():
            params = {}
            
            # Strategy parameters
            param_columns = [
                'rsi_period', 'rsi_oversold', 'rsi_overbought',
                'bb_period', 'bb_std_dev',
                'stop_loss_pct', 'take_profit_pct',
                'ema_fast_period', 'ema_slow_period',
                'position_size_level1', 'position_size_level2', 'position_size_level3'
            ]
            
            for col in param_columns:
                if col in row and pd.notna(row[col]):
                    params[col] = row[col]
                elif col in defaults:
                    params[col] = defaults[col]
            
            # Date overrides (per-row or global)
            params['start_date'] = row.get('start_date', start_date) or "2026-01-02"
            params['end_date'] = row.get('end_date', end_date) or "2026-01-13"
            params['initial_cash'] = row.get('initial_cash', initial_cash) or 100000.0
            
            # Clean up NaN values
            params = {k: v for k, v in params.items() if pd.notna(v)}
            
            # Generate hash for deduplication
            params['_hash'] = self.generate_combination_hash(params)
            params['_row_index'] = idx + 1
            
            combinations.append(params)
        
        # Deduplicate
        seen_hashes = set()
        unique_combinations = []
        for c in combinations:
            if c['_hash'] not in seen_hashes:
                seen_hashes.add(c['_hash'])
                unique_combinations.append(c)
            else:
                print(f"[CSV] Skipping duplicate at row {c['_row_index']}")
        
        print(f"[CSV] {len(unique_combinations)} unique combinations after deduplication")
        return unique_combinations
    
    def _get_parameter_defaults(self) -> Dict[str, Any]:
        """Get default parameter values."""
        return {
            'rsi_period': 14,
            'rsi_oversold': 30.0,
            'rsi_overbought': 70.0,
            'bb_period': 20,
            'bb_std_dev': 2.0,
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.03,
            'ema_fast_period': 9,
            'ema_slow_period': 21,
            'position_size_level1': 0.50,
            'position_size_level2': 0.30,
            'position_size_level3': 0.20,
        }
    
    def _load_completed_hashes(self, run_id: str = None) -> set:
        """Load hashes of already completed backtests for resume capability."""
        if not self.runner.conn:
            self.runner.connect_db()
        
        if not self.runner.conn:
            return set()
        
        try:
            cursor = self.runner.conn.cursor()
            
            # Query BacktestOutcomes for completed runs
            if run_id:
                cursor.execute("""
                    SELECT DISTINCT JSON_VALUE(ParametersJson, '$._hash') as hash
                    FROM BacktestOutcomes
                    WHERE OptimizationRunId = ?
                    AND JSON_VALUE(ParametersJson, '$._hash') IS NOT NULL
                """, (run_id,))
            else:
                cursor.execute("""
                    SELECT DISTINCT JSON_VALUE(ParametersJson, '$._hash') as hash
                    FROM BacktestOutcomes
                    WHERE JSON_VALUE(ParametersJson, '$._hash') IS NOT NULL
                """)
            
            hashes = {row[0] for row in cursor.fetchall() if row[0]}
            print(f"[RESUME] Found {len(hashes)} completed combinations")
            return hashes
            
        except Exception as e:
            print(f"[RESUME] Error loading completed hashes: {e}")
            return set()
    
    # ============================================
    # BATCH EXECUTION
    # ============================================
    
    def run_batch_optimization(
        self,
        combinations: List[Dict[str, Any]],
        run_id: str = None,
        resume: bool = True,
        progress_callback: Callable[[int, int, Dict], None] = None,
        source_file: str = ""
    ) -> OptimizationRun:
        """
        Run batch optimization over multiple parameter combinations.
        
        Args:
            combinations: List of parameter dicts (from load_combinations_from_csv)
            run_id: Optional run ID (auto-generated if None)
            resume: Skip already-completed combinations
            progress_callback: Called after each backtest with (current, total, result)
            source_file: Source CSV/Excel filename for tracking
        
        Returns:
            OptimizationRun with all results
        """
        # Generate run ID
        if not run_id:
            run_id = f"OPT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize run
        self.current_run = OptimizationRun(
            run_id=run_id,
            start_time=datetime.now(),
            total_combinations=len(combinations),
            status="RUNNING",
            source_file=source_file
        )
        
        # Load completed hashes if resuming
        if resume:
            self._completed_hashes = self._load_completed_hashes(run_id)
        else:
            self._completed_hashes = set()
        
        # Store run metadata
        self._store_optimization_run(self.current_run)
        
        print(f"\n{'='*60}")
        print(f"[BATCH] Optimization Run: {run_id}")
        print(f"[BATCH] Total Combinations: {len(combinations)}")
        print(f"[BATCH] Already Completed: {len(self._completed_hashes)}")
        print(f"[BATCH] Remaining: {len(combinations) - len(self._completed_hashes)}")
        print(f"{'='*60}\n")
        
        results = []
        
        for i, params in enumerate(combinations):
            combo_hash = params.get('_hash', self.generate_combination_hash(params))
            
            # Skip if already completed
            if combo_hash in self._completed_hashes:
                print(f"[{i+1}/{len(combinations)}] Skipping (already completed): {combo_hash}")
                self.current_run.completed_combinations += 1
                continue
            
            # Extract backtest params (remove internal keys)
            backtest_params = {k: v for k, v in params.items() if not k.startswith('_')}
            start_date = backtest_params.pop('start_date', '2026-01-02')
            end_date = backtest_params.pop('end_date', '2026-01-13')
            initial_cash = backtest_params.pop('initial_cash', 100000.0)
            
            print(f"\n[{i+1}/{len(combinations)}] Testing: {backtest_params}")
            
            try:
                result = self.runner.run_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash,
                    **backtest_params
                )
                
                if result.get("success"):
                    stats = result.get("statistics", {})
                    
                    sweep_result = SweepResult(
                        params=backtest_params,
                        session_id=result["session_id"],
                        total_return=stats.get("total_return", 0),
                        sharpe_ratio=stats.get("sharpe_ratio", 0),
                        max_drawdown=stats.get("max_drawdown", 0),
                        win_rate=stats.get("win_rate", 0),
                        total_trades=stats.get("total_trades", 0),
                        profit_factor=stats.get("profit_factor", 0),
                        avg_trade_duration=stats.get("avg_trade_duration", 0),
                        combination_hash=combo_hash
                    )
                    
                    results.append(sweep_result)
                    self.current_run.results.append(sweep_result)
                    self._completed_hashes.add(combo_hash)
                    
                    # Update BacktestOutcomes with optimization run ID and hash
                    self._update_backtest_outcome(result["session_id"], run_id, combo_hash, backtest_params)
                    
                    print(f"    ✓ Return: {stats.get('total_return', 0)*100:.2f}%, "
                          f"Sharpe: {stats.get('sharpe_ratio', 0):.2f}, "
                          f"Trades: {stats.get('total_trades', 0)}")
                else:
                    print(f"    ✗ Backtest failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"    ✗ Error: {e}")
            
            self.current_run.completed_combinations += 1
            
            # Progress callback
            if progress_callback:
                progress_callback(
                    self.current_run.completed_combinations,
                    self.current_run.total_combinations,
                    result if 'result' in dir() else {}
                )
        
        # Finalize run
        self.current_run.end_time = datetime.now()
        self.current_run.status = "COMPLETED"
        self._update_optimization_run(self.current_run)
        
        self.results.extend(results)
        
        print(f"\n{'='*60}")
        print(f"[BATCH] Completed: {len(results)} successful backtests")
        print(f"[BATCH] Run ID: {run_id}")
        print(f"{'='*60}\n")
        
        return self.current_run
    
    def _store_optimization_run(self, run: OptimizationRun):
        """Store optimization run metadata in database."""
        if not self.runner.conn:
            self.runner.connect_db()
        
        if not self.runner.conn:
            return
        
        try:
            cursor = self.runner.conn.cursor()
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'OptimizationRuns')
                CREATE TABLE OptimizationRuns (
                    RunId VARCHAR(100) PRIMARY KEY,
                    StartTime DATETIME2,
                    EndTime DATETIME2,
                    TotalCombinations INT,
                    CompletedCombinations INT,
                    Status VARCHAR(20),
                    SourceFile VARCHAR(500),
                    CreatedAt DATETIME2 DEFAULT GETUTCDATE()
                );
                
                INSERT INTO OptimizationRuns (RunId, StartTime, TotalCombinations, CompletedCombinations, Status, SourceFile)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (run.run_id, run.start_time, run.total_combinations, run.completed_combinations, run.status, run.source_file))
            self.runner.conn.commit()
        except Exception as e:
            print(f"[SQL] Error storing optimization run: {e}")
    
    def _update_optimization_run(self, run: OptimizationRun):
        """Update optimization run in database."""
        if not self.runner.conn:
            return
        
        try:
            cursor = self.runner.conn.cursor()
            cursor.execute("""
                UPDATE OptimizationRuns
                SET EndTime = ?, CompletedCombinations = ?, Status = ?
                WHERE RunId = ?
            """, (run.end_time, run.completed_combinations, run.status, run.run_id))
            self.runner.conn.commit()
        except Exception as e:
            print(f"[SQL] Error updating optimization run: {e}")
    
    def _update_backtest_outcome(self, session_id: str, run_id: str, combo_hash: str, params: Dict):
        """Update BacktestOutcomes with optimization run info."""
        if not self.runner.conn:
            return
        
        try:
            cursor = self.runner.conn.cursor()
            
            # Add hash to params for storage
            params_with_hash = {**params, '_hash': combo_hash, '_optimization_run_id': run_id}
            
            cursor.execute("""
                UPDATE BacktestOutcomes
                SET ParametersJson = ?, OptimizationRunId = ?
                WHERE BacktestId = ?
            """, (json.dumps(params_with_hash), run_id, session_id))
            self.runner.conn.commit()
        except Exception as e:
            print(f"[SQL] Error updating backtest outcome: {e}")
    
    # ============================================
    # PARAMETER DEFINITIONS
    # ============================================
    
    @staticmethod
    def get_default_parameter_ranges() -> Dict[str, ParameterRange]:
        """Default parameter ranges for optimization."""
        return {
            # RSI Parameters
            "rsi_period": ParameterRange(
                name="rsi_period",
                values=[10, 12, 14, 16, 18],
                param_type="int"
            ),
            "rsi_oversold": ParameterRange(
                name="rsi_oversold",
                values=[25, 28, 30, 32, 35],
                param_type="float"
            ),
            "rsi_overbought": ParameterRange(
                name="rsi_overbought",
                values=[65, 68, 70, 72, 75],
                param_type="float"
            ),
            
            # Bollinger Band Parameters
            "bb_period": ParameterRange(
                name="bb_period",
                values=[15, 18, 20, 22, 25],
                param_type="int"
            ),
            "bb_std_dev": ParameterRange(
                name="bb_std_dev",
                values=[1.5, 1.75, 2.0, 2.25, 2.5],
                param_type="float"
            ),
            
            # Risk Parameters
            "stop_loss_pct": ParameterRange(
                name="stop_loss_pct",
                values=[0.015, 0.018, 0.02, 0.022, 0.025],
                param_type="float"
            ),
            
            # EMA Parameters (QQQ trend)
            "ema_fast_period": ParameterRange(
                name="ema_fast_period",
                values=[7, 8, 9, 10, 11],
                param_type="int"
            ),
            "ema_slow_period": ParameterRange(
                name="ema_slow_period",
                values=[18, 20, 21, 23, 25],
                param_type="int"
            ),
        }
    
    # ============================================
    # OPTIMIZATION METHODS
    # ============================================
    
    def single_param_sweep(
        self,
        param: ParameterRange,
        start_date: str = "2024-01-01",
        end_date: str = "2024-12-31",
        market_regime: str = "ALL"
    ) -> List[SweepResult]:
        """
        Sweep a single parameter while holding others at defaults.
        
        Results stored in ParameterPerformance for Trade-Mind queries.
        """
        print(f"\n{'='*60}")
        print(f"[SWEEP] Single Parameter: {param.name}")
        print(f"[SWEEP] Values: {param.values}")
        print(f"[SWEEP] Period: {start_date} to {end_date}")
        print(f"{'='*60}\n")
        
        results = []
        
        for value in param.values:
            # Create params dict with single override
            params = {param.name: value}
            
            print(f"\n[TEST] {param.name} = {value}")
            
            result = self.runner.run_backtest(
                start_date=start_date,
                end_date=end_date,
                **params
            )
            
            if result.get("success"):
                stats = result.get("statistics", {})
                
                sweep_result = SweepResult(
                    params={param.name: value},
                    session_id=result["session_id"],
                    total_return=stats.get("total_return", 0),
                    sharpe_ratio=stats.get("sharpe_ratio", 0),
                    max_drawdown=stats.get("max_drawdown", 0),
                    win_rate=stats.get("win_rate", 0),
                    total_trades=stats.get("total_trades", 0),
                    profit_factor=stats.get("profit_factor", 0),
                    avg_trade_duration=stats.get("avg_trade_duration", 0)
                )
                
                results.append(sweep_result)
                
                # Store in SQL for Trade-Mind
                self._store_param_performance(
                    param.name, str(value), market_regime, stats
                )
        
        self.results.extend(results)
        return results
    
    def grid_search(
        self,
        params: List[ParameterRange],
        start_date: str = "2024-01-01",
        end_date: str = "2024-12-31",
        max_combinations: int = 50
    ) -> List[SweepResult]:
        """
        Grid search over multiple parameters.
        
        Warning: Combinations grow exponentially!
        Use max_combinations to limit search space.
        """
        # Generate all combinations
        param_names = [p.name for p in params]
        param_values = [p.values for p in params]
        
        all_combinations = list(itertools.product(*param_values))
        
        if len(all_combinations) > max_combinations:
            print(f"[GRID] Limiting from {len(all_combinations)} to {max_combinations} combinations")
            # Sample evenly from combinations
            step = len(all_combinations) // max_combinations
            all_combinations = all_combinations[::step][:max_combinations]
        
        print(f"\n{'='*60}")
        print(f"[GRID] Parameters: {param_names}")
        print(f"[GRID] Combinations: {len(all_combinations)}")
        print(f"{'='*60}\n")
        
        results = []
        
        for i, values in enumerate(all_combinations):
            params_dict = dict(zip(param_names, values))
            
            print(f"\n[{i+1}/{len(all_combinations)}] Testing: {params_dict}")
            
            result = self.runner.run_backtest(
                start_date=start_date,
                end_date=end_date,
                **params_dict
            )
            
            if result.get("success"):
                stats = result.get("statistics", {})
                
                sweep_result = SweepResult(
                    params=params_dict,
                    session_id=result["session_id"],
                    total_return=stats.get("total_return", 0),
                    sharpe_ratio=stats.get("sharpe_ratio", 0),
                    max_drawdown=stats.get("max_drawdown", 0),
                    win_rate=stats.get("win_rate", 0),
                    total_trades=stats.get("total_trades", 0),
                    profit_factor=stats.get("profit_factor", 0),
                    avg_trade_duration=stats.get("avg_trade_duration", 0)
                )
                
                results.append(sweep_result)
        
        self.results.extend(results)
        return results
    
    def optimize_for_regime(
        self,
        regime: str,
        start_date: str,
        end_date: str,
        params_to_optimize: List[str] = None
    ) -> List[SweepResult]:
        """
        Optimize parameters for a specific market regime.
        
        Regime types: TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY
        
        Results stored in OptimalParameters for regime-specific suggestions.
        """
        if params_to_optimize is None:
            params_to_optimize = ["rsi_oversold", "rsi_overbought", "stop_loss_pct"]
        
        print(f"\n{'='*60}")
        print(f"[REGIME] Optimizing for: {regime}")
        print(f"[REGIME] Parameters: {params_to_optimize}")
        print(f"{'='*60}\n")
        
        all_ranges = self.get_default_parameter_ranges()
        selected_ranges = [all_ranges[p] for p in params_to_optimize if p in all_ranges]
        
        results = self.grid_search(
            selected_ranges,
            start_date=start_date,
            end_date=end_date,
            max_combinations=30
        )
        
        # Find best result
        if results:
            best = max(results, key=lambda r: r.sharpe_ratio)
            
            # Store as optimal for this regime
            self._store_optimal_params(regime, best)
            
            print(f"\n[OPTIMAL] Best for {regime}:")
            print(f"  Params: {best.params}")
            print(f"  Sharpe: {best.sharpe_ratio:.2f}")
            print(f"  Return: {best.total_return*100:.2f}%")
        
        return results
    
    # ============================================
    # SQL STORAGE (Trade-Mind MCP Data)
    # ============================================
    
    def _store_param_performance(
        self,
        param_name: str,
        param_value: str,
        market_regime: str,
        stats: Dict
    ):
        """Store parameter performance for Trade-Mind analysis."""
        if not self.runner.conn:
            self.runner.connect_db()
        
        if not self.runner.conn:
            return
        
        cursor = self.runner.conn.cursor()
        
        try:
            cursor.execute("""
                MERGE ParameterPerformance AS target
                USING (SELECT ? AS ParamName, ? AS ParamValue, ? AS MarketRegime) AS source
                ON target.ParamName = source.ParamName 
                   AND target.ParamValue = source.ParamValue
                   AND target.MarketRegime = source.MarketRegime
                WHEN MATCHED THEN
                    UPDATE SET 
                        TradeCount = TradeCount + ?,
                        WinRate = (WinRate + ?) / 2,
                        AvgPnLWhenUsed = (AvgPnLWhenUsed + ?) / 2,
                        SharpeRatio = (SharpeRatio + ?) / 2,
                        MaxDrawdown = CASE WHEN ? > MaxDrawdown THEN ? ELSE MaxDrawdown END,
                        LastUpdated = GETUTCDATE()
                WHEN NOT MATCHED THEN
                    INSERT (ParamName, ParamValue, MarketRegime, TradeCount, 
                            WinRate, AvgPnLWhenUsed, SharpeRatio, MaxDrawdown)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                # For MERGE match
                param_name, param_value, market_regime,
                # For UPDATE
                stats.get("total_trades", 0),
                stats.get("win_rate", 0),
                stats.get("total_return", 0),
                stats.get("sharpe_ratio", 0),
                stats.get("max_drawdown", 0),
                stats.get("max_drawdown", 0),
                # For INSERT
                param_name, param_value, market_regime,
                stats.get("total_trades", 0),
                stats.get("win_rate", 0),
                stats.get("total_return", 0),
                stats.get("sharpe_ratio", 0),
                stats.get("max_drawdown", 0)
            ))
            
            self.runner.conn.commit()
            
        except Exception as e:
            print(f"[SQL] Error storing param performance: {e}")
    
    def _store_optimal_params(self, regime: str, result: SweepResult):
        """Store optimal parameters for a market regime."""
        if not self.runner.conn:
            return
        
        cursor = self.runner.conn.cursor()
        
        try:
            for param_name, param_value in result.params.items():
                cursor.execute("""
                    MERGE OptimalParameters AS target
                    USING (SELECT ? AS StrategyId, ? AS ParamName, ? AS MarketRegime) AS source
                    ON target.StrategyId = source.StrategyId 
                       AND target.ParamName = source.ParamName
                       AND target.MarketRegime = source.MarketRegime
                    WHEN MATCHED THEN
                        UPDATE SET 
                            OptimalValue = ?,
                            ConfidenceScore = ?,
                            SampleSize = SampleSize + 1,
                            ExpectedSharpe = ?,
                            ExpectedReturn = ?,
                            ExpectedDrawdown = ?,
                            LastCalculated = GETUTCDATE()
                    WHEN NOT MATCHED THEN
                        INSERT (StrategyId, ParamName, MarketRegime, OptimalValue,
                                ConfidenceScore, SampleSize, ExpectedSharpe, 
                                ExpectedReturn, ExpectedDrawdown)
                        VALUES ('TQQQ_SCALPING', ?, ?, ?, 0.7, 1, ?, ?, ?);
                """, (
                    # For MERGE match
                    'TQQQ_SCALPING', param_name, regime,
                    # For UPDATE
                    str(param_value),
                    min(0.95, 0.7 + result.total_trades / 1000),  # Confidence increases with samples
                    result.sharpe_ratio,
                    result.total_return,
                    result.max_drawdown,
                    # For INSERT
                    param_name, regime, str(param_value),
                    result.sharpe_ratio,
                    result.total_return,
                    result.max_drawdown
                ))
            
            self.runner.conn.commit()
            print(f"[SQL] Stored optimal params for regime: {regime}")
            
        except Exception as e:
            print(f"[SQL] Error storing optimal params: {e}")
    
    # ============================================
    # ANALYSIS & REPORTING
    # ============================================
    
    def analyze_results(self) -> Dict[str, Any]:
        """
        Analyze optimization results.
        
        Identifies:
        - Best parameter combinations
        - Parameter sensitivity
        - Risk/reward tradeoffs
        """
        if not self.results:
            return {}
        
        # Sort by Sharpe ratio
        by_sharpe = sorted(self.results, key=lambda r: r.sharpe_ratio, reverse=True)
        
        # Sort by return
        by_return = sorted(self.results, key=lambda r: r.total_return, reverse=True)
        
        # Sort by win rate
        by_winrate = sorted(self.results, key=lambda r: r.win_rate, reverse=True)
        
        # Calculate parameter correlations
        param_impact = self._calculate_param_impact()
        
        return {
            "total_tests": len(self.results),
            "best_by_sharpe": {
                "params": by_sharpe[0].params,
                "sharpe": by_sharpe[0].sharpe_ratio,
                "return": by_sharpe[0].total_return,
                "drawdown": by_sharpe[0].max_drawdown
            } if by_sharpe else None,
            "best_by_return": {
                "params": by_return[0].params,
                "sharpe": by_return[0].sharpe_ratio,
                "return": by_return[0].total_return,
                "drawdown": by_return[0].max_drawdown
            } if by_return else None,
            "best_by_winrate": {
                "params": by_winrate[0].params,
                "sharpe": by_winrate[0].sharpe_ratio,
                "return": by_winrate[0].total_return,
                "win_rate": by_winrate[0].win_rate
            } if by_winrate else None,
            "parameter_impact": param_impact,
            "avg_sharpe": sum(r.sharpe_ratio for r in self.results) / len(self.results),
            "avg_return": sum(r.total_return for r in self.results) / len(self.results),
        }
    
    def _calculate_param_impact(self) -> Dict[str, Dict]:
        """Calculate how each parameter impacts performance."""
        impact = {}
        
        # Group results by each parameter
        for result in self.results:
            for param_name, param_value in result.params.items():
                if param_name not in impact:
                    impact[param_name] = {}
                
                key = str(param_value)
                if key not in impact[param_name]:
                    impact[param_name][key] = {
                        "count": 0,
                        "total_sharpe": 0,
                        "total_return": 0
                    }
                
                impact[param_name][key]["count"] += 1
                impact[param_name][key]["total_sharpe"] += result.sharpe_ratio
                impact[param_name][key]["total_return"] += result.total_return
        
        # Calculate averages
        for param_name, values in impact.items():
            for value_key, data in values.items():
                data["avg_sharpe"] = data["total_sharpe"] / data["count"]
                data["avg_return"] = data["total_return"] / data["count"]
        
        return impact
    
    def export_results(self, output_path: Path):
        """Export optimization results to JSON."""
        analysis = self.analyze_results()
        
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_backtests": len(self.results),
            "analysis": analysis,
            "all_results": [
                {
                    "params": r.params,
                    "session_id": r.session_id,
                    "sharpe": r.sharpe_ratio,
                    "return": r.total_return,
                    "drawdown": r.max_drawdown,
                    "win_rate": r.win_rate,
                    "trades": r.total_trades
                }
                for r in self.results
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"[EXPORT] Results saved: {output_path}")
    
    def print_summary(self):
        """Print optimization summary."""
        analysis = self.analyze_results()
        
        print("\n" + "="*60)
        print("OPTIMIZATION SUMMARY")
        print("="*60)
        print(f"Total Tests: {analysis.get('total_tests', 0)}")
        print(f"Avg Sharpe: {analysis.get('avg_sharpe', 0):.3f}")
        print(f"Avg Return: {analysis.get('avg_return', 0)*100:.2f}%")
        
        if analysis.get("best_by_sharpe"):
            print("\nBest by Sharpe Ratio:")
            best = analysis["best_by_sharpe"]
            print(f"  Params: {best['params']}")
            print(f"  Sharpe: {best['sharpe']:.3f}")
            print(f"  Return: {best['return']*100:.2f}%")
            print(f"  Max DD: {best['drawdown']*100:.2f}%")
        
        print("\n" + "="*60)


# ============================================
# CLI ENTRY POINT
# ============================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="TQQQ Parameter Optimizer")
    parser.add_argument("--mode", choices=["single", "grid", "regime", "csv"], default="single")
    parser.add_argument("--param", default="rsi_oversold", help="Parameter to sweep (single mode)")
    parser.add_argument("--values", default="25,28,30,32,35", help="Values to test")
    parser.add_argument("--regime", default="ALL", help="Market regime for optimization")
    parser.add_argument("--start", default="2026-01-02", help="Start date")
    parser.add_argument("--end", default="2026-01-13", help="End date")
    parser.add_argument("--output", default="optimization_results.json", help="Output file")
    parser.add_argument("--csv-file", default="parameter_combinations.csv", help="CSV file with parameter combinations")
    parser.add_argument("--no-resume", action="store_true", help="Don't skip completed combinations")
    
    args = parser.parse_args()
    
    optimizer = ParameterOptimizer()
    
    if args.mode == "single":
        # Single parameter sweep
        values = [float(v) if '.' in v else int(v) for v in args.values.split(",")]
        param = ParameterRange(name=args.param, values=values)
        
        optimizer.single_param_sweep(
            param,
            start_date=args.start,
            end_date=args.end,
            market_regime=args.regime
        )
        
    elif args.mode == "grid":
        # Grid search over key parameters
        all_ranges = optimizer.get_default_parameter_ranges()
        params = [
            all_ranges["rsi_oversold"],
            all_ranges["rsi_overbought"],
            all_ranges["stop_loss_pct"]
        ]
        
        optimizer.grid_search(
            params,
            start_date=args.start,
            end_date=args.end,
            max_combinations=25
        )
        
    elif args.mode == "regime":
        # Regime-specific optimization
        optimizer.optimize_for_regime(
            args.regime,
            start_date=args.start,
            end_date=args.end
        )
    
    elif args.mode == "csv":
        # Load from CSV and run batch optimization
        csv_path = Path(args.csv_file)
        if not csv_path.exists():
            print(f"[ERROR] CSV file not found: {csv_path}")
            return
        
        print(f"[CSV] Loading combinations from: {csv_path}")
        combinations = optimizer.load_combinations_from_csv(
            str(csv_path),
            start_date=args.start,
            end_date=args.end
        )
        
        print(f"[CSV] Running batch optimization with {len(combinations)} combinations")
        optimizer.run_batch_optimization(
            combinations,
            resume=not args.no_resume,
            source_file=str(csv_path)
        )
    
    # Print and export results
    optimizer.print_summary()
    optimizer.export_results(Path(args.output))
    
    print("\n[INFO] Results stored in SQL - available via Trade-Mind MCP")
    print("[INFO] Use sp_SuggestCorrections to get parameter recommendations")


if __name__ == "__main__":
    main()

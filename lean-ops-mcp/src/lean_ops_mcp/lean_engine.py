"""
LEAN Engine Interface
=====================
Interface to QuantConnect LEAN for backtest execution.
"""

import os
import sys
import json
import uuid
import subprocess
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Results from a LEAN backtest run."""
    session_id: str
    success: bool
    
    # Performance metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Equity
    starting_equity: float = 0.0
    ending_equity: float = 0.0
    
    # Metadata
    start_date: str = ""
    end_date: str = ""
    algorithm_name: str = ""
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    
    # Paths to result files
    results_file: Optional[str] = None
    log_file: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class LeanEngine:
    """
    Interface to QuantConnect LEAN engine.
    
    Handles:
    - Backtest execution
    - Results parsing
    - Parameter configuration
    """
    
    def __init__(self):
        self.config = get_config().lean
        self.lean_path = self.config.lean_path
        self.algorithm_path = self.config.algorithm_path
        self.results_path = self.config.results_path
        
    def _generate_session_id(self, prefix: str = "BT") -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{unique_id}"
    
    def _create_config_file(
        self,
        session_id: str,
        algorithm_name: str,
        start_date: str,
        end_date: str,
        initial_cash: float,
        parameters: Dict[str, Any]
    ) -> Path:
        """Create LEAN configuration file for backtest."""
        config = {
            "environment": "backtesting",
            "algorithm-type-name": algorithm_name,
            "algorithm-language": "Python",
            "algorithm-location": str(self.algorithm_path / f"{algorithm_name}.py"),
            
            "data-folder": str(self.config.data_path),
            "results-destination-folder": str(self.results_path / session_id),
            
            "log-handler": "QuantConnect.Logging.CompositeLogHandler",
            "messaging-handler": "QuantConnect.Messaging.Messaging",
            "job-queue-handler": "QuantConnect.Queues.JobQueue",
            "api-handler": "QuantConnect.Api.Api",
            
            # Backtest settings
            "start-date": start_date,
            "end-date": end_date,
            "cash-amount": initial_cash,
            
            # Algorithm parameters
            "parameters": parameters,
            
            # Output settings
            "results-destination-folder": str(self.results_path / session_id),
        }
        
        # Create results directory
        results_dir = self.results_path / session_id
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Write config
        config_file = results_dir / "config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        
        return config_file
    
    def _parse_results(self, session_id: str, start_time: datetime) -> BacktestResult:
        """Parse LEAN backtest results."""
        results_dir = self.results_path / session_id
        result_file = results_dir / f"{session_id}.json"
        
        result = BacktestResult(
            session_id=session_id,
            success=False,
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
        
        if not result_file.exists():
            # Check for alternative result file names
            json_files = list(results_dir.glob("*.json"))
            result_files = [f for f in json_files if f.name != "config.json"]
            if result_files:
                result_file = result_files[0]
            else:
                result.error_message = "No result file found"
                return result
        
        try:
            with open(result_file, "r") as f:
                data = json.load(f)
            
            result.results_file = str(result_file)
            
            # Parse statistics
            stats = data.get("Statistics", {})
            result.total_return = self._parse_percentage(stats.get("Total Net Profit", "0%"))
            result.sharpe_ratio = float(stats.get("Sharpe Ratio", 0) or 0)
            result.max_drawdown = abs(self._parse_percentage(stats.get("Drawdown", "0%")))
            result.win_rate = self._parse_percentage(stats.get("Win Rate", "0%"))
            result.profit_factor = float(stats.get("Profit-Loss Ratio", 0) or 0)
            
            result.total_trades = int(stats.get("Total Orders", 0) or 0)
            result.winning_trades = int(stats.get("Winning Trades", 0) or 0) if "Winning Trades" in stats else 0
            result.losing_trades = int(stats.get("Losing Trades", 0) or 0) if "Losing Trades" in stats else 0
            
            # Parse equity
            result.starting_equity = float(stats.get("Starting Portfolio Value", 0) or 0)
            result.ending_equity = float(stats.get("Ending Portfolio Value", 0) or 0)
            
            # Metadata
            result.start_date = data.get("PeriodStart", "")
            result.end_date = data.get("PeriodFinish", "")
            result.algorithm_name = data.get("AlgorithmName", "")
            
            result.success = True
            
        except Exception as e:
            result.error_message = f"Failed to parse results: {str(e)}"
            logger.error(result.error_message)
        
        return result
    
    def _parse_percentage(self, value: str) -> float:
        """Parse percentage string to float."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("%", "").replace(",", "")) / 100
        except (ValueError, TypeError):
            return 0.0
    
    def run_backtest(
        self,
        algorithm_name: str,
        start_date: str,
        end_date: str,
        initial_cash: float = 100000.0,
        parameters: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> BacktestResult:
        """
        Execute a LEAN backtest.
        
        Args:
            algorithm_name: Name of the algorithm class (e.g., "TQQQScalpingAlgorithm")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_cash: Starting capital
            parameters: Strategy parameters to override
            session_id: Optional session ID (auto-generated if not provided)
        
        Returns:
            BacktestResult with performance metrics and trade details
        """
        session_id = session_id or self._generate_session_id()
        parameters = parameters or {}
        start_time = datetime.now()
        
        logger.info(f"Starting backtest {session_id}: {algorithm_name} [{start_date} to {end_date}]")
        
        # Create config file
        config_file = self._create_config_file(
            session_id=session_id,
            algorithm_name=algorithm_name,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            parameters=parameters
        )
        
        # Build LEAN command
        # Check for different execution methods
        launcher_dll = self.lean_path / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.dll"
        launcher_exe = self.lean_path / "Launcher" / "bin" / "Debug" / "QuantConnect.Lean.Launcher.exe"
        
        if launcher_dll.exists():
            cmd = ["dotnet", str(launcher_dll), "--config", str(config_file)]
        elif launcher_exe.exists():
            cmd = [str(launcher_exe), "--config", str(config_file)]
        else:
            # Try docker-based execution
            logger.warning("LEAN launcher not found - attempting Docker execution")
            return self._run_backtest_docker(
                session_id, algorithm_name, start_date, end_date,
                initial_cash, parameters, start_time
            )
        
        # Execute backtest
        try:
            logger.info(f"Executing: {' '.join(cmd)}")
            process = subprocess.run(
                cmd,
                cwd=str(self.lean_path),
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Save log output
            log_file = self.results_path / session_id / "backtest.log"
            with open(log_file, "w") as f:
                f.write(f"STDOUT:\n{process.stdout}\n\nSTDERR:\n{process.stderr}")
            
            if process.returncode != 0:
                result = BacktestResult(
                    session_id=session_id,
                    success=False,
                    error_message=f"LEAN exited with code {process.returncode}: {process.stderr[:500]}",
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    log_file=str(log_file)
                )
                return result
            
        except subprocess.TimeoutExpired:
            return BacktestResult(
                session_id=session_id,
                success=False,
                error_message="Backtest timed out after 1 hour",
                duration_seconds=3600
            )
        except Exception as e:
            return BacktestResult(
                session_id=session_id,
                success=False,
                error_message=f"Failed to execute backtest: {str(e)}",
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
        
        # Parse results
        result = self._parse_results(session_id, start_time)
        result.log_file = str(log_file)
        
        logger.info(f"Backtest {session_id} completed: Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}")
        
        return result
    
    def _run_backtest_docker(
        self,
        session_id: str,
        algorithm_name: str,
        start_date: str,
        end_date: str,
        initial_cash: float,
        parameters: Dict[str, Any],
        start_time: datetime
    ) -> BacktestResult:
        """Run backtest using Docker (fallback method)."""
        # This is a placeholder for Docker-based execution
        # Implement if needed for environments without .NET SDK
        return BacktestResult(
            session_id=session_id,
            success=False,
            error_message="LEAN launcher not found and Docker execution not implemented",
            duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    
    def get_available_algorithms(self) -> List[str]:
        """List available Python algorithms."""
        algorithms = []
        if self.algorithm_path.exists():
            for py_file in self.algorithm_path.glob("*.py"):
                if not py_file.name.startswith("_"):
                    algorithms.append(py_file.stem)
        return sorted(algorithms)
    
    def validate_algorithm(self, algorithm_name: str) -> bool:
        """Check if algorithm file exists."""
        algo_file = self.algorithm_path / f"{algorithm_name}.py"
        return algo_file.exists()


# Global engine instance
_engine: Optional[LeanEngine] = None


def get_engine() -> LeanEngine:
    """Get the global LEAN engine instance."""
    global _engine
    if _engine is None:
        _engine = LeanEngine()
    return _engine

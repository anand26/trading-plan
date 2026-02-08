"""
TQQQ/SQQQ Trading System - Results Processor
=============================================
Parses LEAN backtest output and populates SQL for Trade-Mind MCP.

This module provides detailed parsing of LEAN results to extract:
- Individual trades with entry/exit details
- Signal effectiveness metrics
- Daily performance aggregates
- Parameter correlation data

All data is structured to support Trade-Mind MCP queries.
"""

import json
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    import pyodbc
except ImportError:
    pyodbc = None  # type: ignore


@dataclass
class ParsedTrade:
    """Structured trade data for SQL storage."""
    symbol: str
    side: str  # BUY or SELL (direction of entry)
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    realized_pnl: float
    realized_pnl_pct: float
    duration_seconds: int
    entry_reason: str = ""
    exit_reason: str = ""
    commission: float = 0.0


@dataclass
class ParsedSignal:
    """Structured signal data for analysis."""
    symbol: str
    timestamp: datetime
    signal_type: str  # ENTRY, EXIT, PYRAMID
    direction: str  # LONG, SHORT
    strength: float
    rsi_value: Optional[float] = None
    vwap_distance: Optional[float] = None
    bb_position: Optional[float] = None
    qqq_trend: Optional[str] = None
    was_acted_on: bool = False
    reason_not_acted: Optional[str] = None


class LeanResultsProcessor:
    """
    Process LEAN backtest results for Trade-Mind MCP integration.
    
    Key responsibilities:
    1. Parse LEAN JSON output format
    2. Parse transaction CSV logs
    3. Extract metrics for each Trade-Mind MCP tool
    4. Structure data for SQL storage
    """
    
    def __init__(self, results_dir: Path, session_id: str):
        self.results_dir = Path(results_dir)
        self.session_id = session_id
        self.trades: List[ParsedTrade] = []
        self.signals: List[ParsedSignal] = []
        self.daily_stats: Dict[str, Dict] = {}
        self.statistics: Dict[str, Any] = {}
    
    # ============================================
    # LEAN OUTPUT PARSING
    # ============================================
    
    def parse_all(self) -> bool:
        """Parse all available LEAN output files."""
        try:
            # 1. Parse main results JSON
            self._parse_results_json()
            
            # 2. Parse transaction log CSV (if exists)
            self._parse_transaction_log()
            
            # 3. Parse algorithm logs for signals (if exists)
            self._parse_algorithm_logs()
            
            # 4. Calculate daily aggregates
            self._calculate_daily_stats()
            
            return True
        except Exception as e:
            print(f"[PARSE] Error: {e}")
            return False
    
    def _parse_results_json(self):
        """Parse the main LEAN results JSON file."""
        # Find results file (not config.json)
        json_files = [f for f in self.results_dir.glob("*.json") if f.name != "config.json"]
        
        if not json_files:
            print(f"[PARSE] No results JSON found in {self.results_dir}")
            return
        
        results_file = json_files[0]
        print(f"[PARSE] Reading: {results_file}")
        
        with open(results_file, 'r') as f:
            data = json.load(f)
        
        # Extract statistics
        self.statistics = self._extract_statistics(data)
        
        # Extract trades from Orders
        self._extract_trades_from_orders(data.get("Orders", {}))
        
        # Extract chart data if needed for signals
        self._extract_from_charts(data.get("Charts", {}))
    
    def _extract_statistics(self, data: Dict) -> Dict[str, Any]:
        """Extract performance statistics from LEAN results."""
        stats = data.get("Statistics", {})
        runtime = data.get("RuntimeStatistics", {})
        
        def parse_value(val, default=0.0):
            """Parse string values to float."""
            if val is None:
                return default
            if isinstance(val, (int, float)):
                return float(val)
            # Remove $, %, commas
            cleaned = re.sub(r'[$,%]', '', str(val))
            try:
                return float(cleaned)
            except:
                return default
        
        return {
            # Core metrics for Trade-Mind MCP
            "total_return": parse_value(stats.get("Total Net Profit")) / 100,
            "sharpe_ratio": parse_value(stats.get("Sharpe Ratio")),
            "sortino_ratio": parse_value(stats.get("Sortino Ratio")),
            "max_drawdown": parse_value(stats.get("Drawdown")) / 100,
            "total_trades": int(parse_value(stats.get("Total Trades"))),
            "win_rate": parse_value(stats.get("Win Rate")) / 100,
            "profit_factor": parse_value(stats.get("Profit-Loss Ratio")),
            
            # Trade metrics
            "avg_win": parse_value(stats.get("Average Win")),
            "avg_loss": parse_value(stats.get("Average Loss")),
            "avg_trade_duration": parse_value(stats.get("Average Trade Duration")),
            "largest_win": parse_value(stats.get("Largest Win")),
            "largest_loss": parse_value(stats.get("Largest Loss")),
            
            # Portfolio metrics
            "equity_final": parse_value(runtime.get("Equity")),
            "cagr": parse_value(stats.get("Compounding Annual Return")) / 100,
            "information_ratio": parse_value(stats.get("Information Ratio")),
            "treynor_ratio": parse_value(stats.get("Treynor Ratio")),
            
            # Trading metrics
            "long_trades": int(parse_value(stats.get("Total Long Trades", 0))),
            "short_trades": int(parse_value(stats.get("Total Short Trades", 0))),
            "winning_trades": int(parse_value(stats.get("Winning Trades", 0))),
            "losing_trades": int(parse_value(stats.get("Losing Trades", 0))),
        }
    
    def _extract_trades_from_orders(self, orders: Dict):
        """
        Extract trade pairs from LEAN orders.
        
        LEAN stores orders, not round-trip trades.
        We need to pair entry orders with exit orders.
        """
        # Group orders by symbol
        orders_by_symbol: Dict[str, List] = {}
        
        for order_id, order in orders.items():
            symbol = order.get("Symbol", {}).get("Value", "UNKNOWN")
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            
            orders_by_symbol[symbol].append({
                "order_id": order_id,
                "type": order.get("Type", ""),
                "status": order.get("Status", ""),
                "quantity": order.get("Quantity", 0),
                "price": order.get("Price", 0),
                "time": order.get("Time", ""),
                "direction": order.get("Direction", ""),
                "tag": order.get("Tag", "")  # Contains entry/exit reason
            })
        
        # Match entries with exits for each symbol
        for symbol, symbol_orders in orders_by_symbol.items():
            self._pair_orders_to_trades(symbol, symbol_orders)
    
    def _pair_orders_to_trades(self, symbol: str, orders: List[Dict]):
        """Pair buy/sell orders into complete trades."""
        # Sort by time
        orders.sort(key=lambda x: x.get("time", ""))
        
        position_stack: List[Dict] = []  # Stack for FIFO matching
        
        for order in orders:
            if order.get("status") != "Filled":
                continue
            
            qty = abs(order.get("quantity", 0))
            direction = order.get("direction", "")
            
            # Determine if this is an entry or exit
            is_entry = (
                (direction == "Buy" and len(position_stack) == 0) or
                (direction == "Buy" and position_stack[-1].get("direction") == "Buy") or
                (direction == "Sell" and len(position_stack) == 0) or
                (direction == "Sell" and position_stack[-1].get("direction") == "Sell")
            )
            
            if is_entry or len(position_stack) == 0:
                # This is an entry - add to stack
                position_stack.append(order)
            else:
                # This is an exit - match with entry
                if position_stack:
                    entry_order = position_stack.pop(0)  # FIFO
                    trade = self._create_trade_from_orders(symbol, entry_order, order)
                    if trade:
                        self.trades.append(trade)
    
    def _create_trade_from_orders(
        self,
        symbol: str,
        entry: Dict,
        exit: Dict
    ) -> Optional[ParsedTrade]:
        """Create a ParsedTrade from entry and exit orders."""
        try:
            entry_time = datetime.fromisoformat(entry.get("time", "").replace("Z", "+00:00"))
            exit_time = datetime.fromisoformat(exit.get("time", "").replace("Z", "+00:00"))
            
            entry_price = float(entry.get("price", 0))
            exit_price = float(exit.get("price", 0))
            quantity = abs(float(entry.get("quantity", 0)))
            
            # Determine side and PnL
            if entry.get("direction") == "Buy":
                side = "BUY"
                pnl = (exit_price - entry_price) * quantity
            else:
                side = "SELL"
                pnl = (entry_price - exit_price) * quantity
            
            pnl_pct = pnl / (entry_price * quantity) if entry_price > 0 else 0
            
            return ParsedTrade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                entry_time=entry_time,
                exit_time=exit_time,
                realized_pnl=pnl,
                realized_pnl_pct=pnl_pct,
                duration_seconds=int((exit_time - entry_time).total_seconds()),
                entry_reason=entry.get("tag", ""),
                exit_reason=exit.get("tag", "")
            )
        except Exception as e:
            print(f"[PARSE] Error creating trade: {e}")
            return None
    
    def _parse_transaction_log(self):
        """Parse the transactions.csv file if it exists."""
        csv_path = self.results_dir / "transactions.csv"
        
        if not csv_path.exists():
            print(f"[PARSE] No transaction log found: {csv_path}")
            return
        
        print(f"[PARSE] Reading transactions: {csv_path}")
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # CSV has direct trade records
                # This is an alternative to parsing Orders
                pass  # Trades already extracted from JSON
    
    def _parse_algorithm_logs(self):
        """
        Parse algorithm log files for signal data.
        
        Our TQQQScalpingAlgorithm logs signals with specific format:
        [SIGNAL] ENTRY LONG TQQQ RSI=28.5 VWAP_DIST=-0.02 ...
        """
        log_files = list(self.results_dir.glob("*.log")) + \
                    list(self.results_dir.glob("*-log.txt"))
        
        signal_pattern = re.compile(
            r'\[SIGNAL\]\s+(\w+)\s+(\w+)\s+(\w+)\s+'
            r'RSI=([\d.]+)\s+VWAP_DIST=([-\d.]+)\s*'
            r'(?:BB=([-\d.]+))?\s*(?:QQQ_TREND=(\w+))?'
        )
        
        for log_file in log_files:
            print(f"[PARSE] Scanning for signals: {log_file}")
            
            with open(log_file, 'r') as f:
                for line in f:
                    match = signal_pattern.search(line)
                    if match:
                        signal = ParsedSignal(
                            symbol=match.group(3),
                            timestamp=datetime.now(),  # Would need to parse from log
                            signal_type=match.group(1),  # ENTRY, EXIT, PYRAMID
                            direction=match.group(2),  # LONG, SHORT
                            strength=0.8,  # Would calculate from indicators
                            rsi_value=float(match.group(4)),
                            vwap_distance=float(match.group(5)),
                            bb_position=float(match.group(6)) if match.group(6) else None,
                            qqq_trend=match.group(7),
                            was_acted_on=True
                        )
                        self.signals.append(signal)
    
    def _extract_from_charts(self, charts: Dict):
        """Extract useful data from LEAN chart output."""
        # Could extract equity curve, drawdown series, etc.
        pass
    
    def _calculate_daily_stats(self):
        """Calculate daily performance aggregates from trades."""
        for trade in self.trades:
            date_key = trade.exit_time.strftime("%Y-%m-%d")
            
            if date_key not in self.daily_stats:
                self.daily_stats[date_key] = {
                    "date": trade.exit_time.date(),
                    "trade_count": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "realized_pnl": 0.0,
                    "volume": 0.0
                }
            
            day = self.daily_stats[date_key]
            day["trade_count"] += 1
            day["realized_pnl"] += trade.realized_pnl
            day["volume"] += trade.quantity * trade.entry_price
            
            if trade.realized_pnl > 0:
                day["win_count"] += 1
            elif trade.realized_pnl < 0:
                day["loss_count"] += 1
    
    # ============================================
    # SQL STORAGE (Trade-Mind MCP Data Source)
    # ============================================
    
    def store_to_sql(self, conn: Any) -> bool:
        """
        Store all parsed data to SQL Server.
        
        Tables populated:
        - Trades → sp_GetLastTrades, sp_CalculateWinRate
        - Signals → v_SignalOutcomes, signal analysis
        - DailyPerformance → sp_GetDailyPnL
        - BacktestOutcomes → parameter comparison
        """
        cursor = conn.cursor()
        
        try:
            # 1. Store trades
            for trade in self.trades:
                cursor.execute("""
                    INSERT INTO Trades (
                        SessionId, Symbol, Side, Quantity,
                        EntryPrice, ExitPrice, RealizedPnL, RealizedPnLPct,
                        EntryTime, ExitTime, Duration,
                        EntryReason, ExitReason, Commission,
                        AvgEntryPrice, AvgExitPrice
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    trade.symbol,
                    trade.side,
                    trade.quantity,
                    trade.entry_price,
                    trade.exit_price,
                    trade.realized_pnl,
                    trade.realized_pnl_pct,
                    trade.entry_time,
                    trade.exit_time,
                    trade.duration_seconds,
                    trade.entry_reason,
                    trade.exit_reason,
                    trade.commission,
                    trade.entry_price,
                    trade.exit_price
                ))
            
            print(f"[SQL] Stored {len(self.trades)} trades")
            
            # 2. Store signals
            for signal in self.signals:
                cursor.execute("""
                    INSERT INTO Signals (
                        SessionId, Symbol, Timestamp,
                        SignalType, Direction, Strength,
                        RsiValue, VwapDistance, BbPosition, QqqTrend,
                        WasActedOn, ReasonNotActed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    signal.symbol,
                    signal.timestamp,
                    signal.signal_type,
                    signal.direction,
                    signal.strength,
                    signal.rsi_value,
                    signal.vwap_distance,
                    signal.bb_position,
                    signal.qqq_trend,
                    signal.was_acted_on,
                    signal.reason_not_acted
                ))
            
            print(f"[SQL] Stored {len(self.signals)} signals")
            
            # 3. Store daily performance
            for date_key, day in self.daily_stats.items():
                cursor.execute("""
                    INSERT INTO DailyPerformance (
                        SessionId, TradingDate,
                        TradeCount, WinCount, LossCount,
                        RealizedPnL, VolumeTraded
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.session_id,
                    day["date"],
                    day["trade_count"],
                    day["win_count"],
                    day["loss_count"],
                    day["realized_pnl"],
                    day["volume"]
                ))
            
            print(f"[SQL] Stored {len(self.daily_stats)} daily records")
            
            # 4. Store backtest outcome summary with derived metrics
            win_rate = self.statistics.get("win_rate", 0)
            avg_win = self.statistics.get("avg_win", 0)
            avg_loss = abs(self.statistics.get("avg_loss", 0))
            sharpe = self.statistics.get("sharpe_ratio", 0)
            max_dd = self.statistics.get("max_drawdown", 0)
            total_trades = self.statistics.get("total_trades", 0)
            
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss) if total_trades > 0 else 0
            expectancy_ratio = expectancy / avg_loss if avg_loss > 0 else 0
            
            if sharpe >= 2.0: grade = 'A'
            elif sharpe >= 1.5: grade = 'B+'
            elif sharpe >= 1.0: grade = 'B'
            elif sharpe >= 0.5: grade = 'C+'
            elif sharpe >= 0: grade = 'C'
            else: grade = 'D'
            
            is_successful = 1 if (sharpe >= 1.0 and win_rate >= 0.4 and abs(max_dd) <= 0.20) else 0
            
            cursor.execute("""
                INSERT INTO BacktestOutcomes (
                    SessionId, TotalReturn, SharpeRatio, MaxDrawdown,
                    TotalTrades, WinRate, ProfitFactor,
                    Expectancy, ExpectancyRatio, PerformanceGrade, IsSuccessful
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_id,
                self.statistics.get("total_return", 0),
                self.statistics.get("sharpe_ratio", 0),
                self.statistics.get("max_drawdown", 0),
                self.statistics.get("total_trades", 0),
                self.statistics.get("win_rate", 0),
                self.statistics.get("profit_factor", 0),
                expectancy, expectancy_ratio, grade, is_successful
            ))
            
            conn.commit()
            print(f"[SQL] All data stored for session: {self.session_id}")
            return True
            
        except Exception as e:
            print(f"[SQL] Error: {e}")
            conn.rollback()
            return False
    
    # ============================================
    # TRADE-MIND MCP DATA EXPORT
    # ============================================
    
    def get_trade_mind_data(self) -> Dict[str, Any]:
        """
        Export data in format ready for Trade-Mind MCP tools.
        
        Returns dict with data structured for each MCP tool:
        - get_last_trades: List of recent trades
        - calculate_win_rate: Win/loss statistics
        - get_daily_pnl: Daily P&L records
        """
        return {
            "session_id": self.session_id,
            
            # For sp_GetLastTrades
            "trades": [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "realized_pnl": t.realized_pnl,
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat(),
                    "duration_minutes": t.duration_seconds / 60,
                    "entry_reason": t.entry_reason,
                    "exit_reason": t.exit_reason
                }
                for t in self.trades
            ],
            
            # For sp_CalculateWinRate
            "win_rate_stats": {
                "total_trades": len(self.trades),
                "winning_trades": sum(1 for t in self.trades if t.realized_pnl > 0),
                "losing_trades": sum(1 for t in self.trades if t.realized_pnl < 0),
                "win_rate": self.statistics.get("win_rate", 0),
                "avg_win": self.statistics.get("avg_win", 0),
                "avg_loss": self.statistics.get("avg_loss", 0),
                "profit_factor": self.statistics.get("profit_factor", 0),
                "total_pnl": sum(t.realized_pnl for t in self.trades)
            },
            
            # For sp_GetDailyPnL
            "daily_pnl": [
                {
                    "date": date_key,
                    "trade_count": day["trade_count"],
                    "win_count": day["win_count"],
                    "loss_count": day["loss_count"],
                    "realized_pnl": day["realized_pnl"],
                    "win_rate": day["win_count"] / day["trade_count"] if day["trade_count"] > 0 else 0
                }
                for date_key, day in sorted(self.daily_stats.items())
            ],
            
            # Summary statistics
            "statistics": self.statistics
        }
    
    def export_to_json(self, output_path: Path) -> bool:
        """Export Trade-Mind data to JSON file."""
        data = self.get_trade_mind_data()
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"[EXPORT] Trade-Mind data: {output_path}")
        return True


# ============================================
# STANDALONE USAGE
# ============================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python results_processor.py <results_dir> <session_id>")
        sys.exit(1)
    
    results_dir = Path(sys.argv[1])
    session_id = sys.argv[2] if len(sys.argv) > 2 else "TEST_SESSION"
    
    processor = LeanResultsProcessor(results_dir, session_id)
    
    if processor.parse_all():
        # Export to JSON
        output_path = results_dir / "trade_mind_data.json"
        processor.export_to_json(output_path)
        
        # Print summary
        data = processor.get_trade_mind_data()
        print("\n" + "="*50)
        print("TRADE-MIND DATA SUMMARY")
        print("="*50)
        print(f"Total Trades: {len(data['trades'])}")
        print(f"Win Rate: {data['win_rate_stats']['win_rate']*100:.1f}%")
        print(f"Total P&L: ${data['win_rate_stats']['total_pnl']:,.2f}")
        print(f"Daily Records: {len(data['daily_pnl'])}")

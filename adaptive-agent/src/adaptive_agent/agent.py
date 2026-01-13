"""
Adaptive Agent - Main Orchestration Class

Ties together Observer, Analyzer, Executor, and Decision Engine
into a cohesive agent that monitors and adapts trading strategy.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import AgentConfig, get_config
from .models import (
    AgentState,
    AgentMode,
    CycleResult,
    Decision,
    DecisionType,
    MarketRegime,
)
from .observer import Observer
from .analyzer import Analyzer
from .executor import Executor
from .decision_engine import DecisionEngine


logger = logging.getLogger(__name__)


class AdaptiveAgent:
    """
    Main adaptive trading agent.
    
    Orchestrates the observe → analyze → decide → execute loop
    to continuously adapt trading strategy based on market conditions
    and learned patterns.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or get_config()
        
        # Initialize components
        self.observer = Observer(self.config)
        self.analyzer = Analyzer(self.config)
        self.executor = Executor(self.config)
        self.decision_engine = DecisionEngine(self.config)
        
        # Initialize state
        self.state = AgentState(
            agent_id=f"adaptive-agent-{uuid4().hex[:8]}",
            mode=AgentMode(self.config.mode),
        )
        
        # Scheduler for periodic cycles
        self._scheduler: Optional[AsyncIOScheduler] = None
        
        # Callbacks
        self._on_decision: Optional[Callable[[Decision], None]] = None
        self._on_cycle_complete: Optional[Callable[[CycleResult], None]] = None
    
    @property
    def is_running(self) -> bool:
        return self.state.is_running
    
    def on_decision(self, callback: Callable[[Decision], None]):
        """Register a callback for when decisions are made."""
        self._on_decision = callback
    
    def on_cycle_complete(self, callback: Callable[[CycleResult], None]):
        """Register a callback for when cycles complete."""
        self._on_cycle_complete = callback
    
    async def start(self):
        """Start the agent's main loop."""
        if self.state.is_running:
            logger.warning("Agent is already running")
            return
        
        logger.info(f"Starting Adaptive Agent in {self.config.mode} mode")
        
        self.state.is_running = True
        self.state.started_at = datetime.now()
        
        # Create scheduler
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._run_cycle,
            IntervalTrigger(seconds=self.config.cycle_interval_seconds),
            id="main_cycle",
            name="Main Agent Cycle",
        )
        
        self._scheduler.start()
        
        # Run first cycle immediately
        await self._run_cycle()
        
        logger.info(f"Agent started. Cycle interval: {self.config.cycle_interval_seconds}s")
    
    async def stop(self):
        """Stop the agent."""
        if not self.state.is_running:
            return
        
        logger.info("Stopping Adaptive Agent")
        
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        
        self.state.is_running = False
        
        # Close component connections
        self.observer.close()
        self.analyzer.close()
        self.executor.close()
        self.decision_engine.close()
        
        logger.info("Agent stopped")
    
    def pause(self):
        """Pause the agent (stops processing but keeps running)."""
        self.state.is_paused = True
        logger.info("Agent paused")
    
    def resume(self):
        """Resume a paused agent."""
        self.state.is_paused = False
        logger.info("Agent resumed")
    
    async def _run_cycle(self):
        """Run a single agent cycle."""
        if self.state.is_paused:
            logger.debug("Agent is paused, skipping cycle")
            return
        
        cycle_start = datetime.now()
        errors = []
        
        try:
            # Phase 1: Observe
            market, positions, performance = self.observer.get_full_context()
            
            # Update state with current regime
            self.state.current_regime = market.regime
            self.state.current_positions = positions
            
            # Check for emergency conditions early
            if performance.current_drawdown > self.config.thresholds.emergency_drawdown_pct:
                if not self.state.emergency_stop_active:
                    logger.warning(
                        f"Emergency drawdown threshold breached: "
                        f"{performance.current_drawdown:.1%}"
                    )
                    emergency_decision = Decision(
                        decision_type=DecisionType.EMERGENCY_STOP,
                        action="HALT_TRADING",
                        confidence=1.0,
                        reasoning=f"Drawdown {performance.current_drawdown:.1%} exceeded threshold",
                        market_snapshot=market,
                        performance_snapshot=performance,
                    )
                    self.executor.execute(emergency_decision)
                    self.state.emergency_stop_active = True
                    self.state.emergency_stop_reason = emergency_decision.reasoning
                    
                    if self._on_decision:
                        self._on_decision(emergency_decision)
                    
                    return
            
            # Phase 2: Analyze
            observations = self.analyzer.analyze_market_conditions(market, performance)
            matched_patterns = self.analyzer.match_patterns(market, performance)
            recommendations = self.analyzer.get_active_recommendations()
            risk_assessment = self.analyzer.assess_risk(market, positions, performance)
            
            # Phase 3: Decide
            # Use both analyzer and decision engine
            analyzer_decision = self.analyzer.generate_decision(
                market, positions, performance,
                observations, matched_patterns, recommendations, risk_assessment
            )
            
            engine_decision = self.decision_engine.evaluate(market, positions, performance)
            
            # Merge decisions - prefer higher confidence
            decision = self._merge_decisions(analyzer_decision, engine_decision)
            
            # Phase 4: Execute
            if decision.decision_type != DecisionType.NO_ACTION:
                decision = self.executor.execute(decision)
                
                if decision.executed:
                    self.state.decisions_executed += 1
                    if decision.decision_type == DecisionType.PARAMETER_ADJUSTMENT:
                        self.state.parameter_changes_today += 1
            
            self.state.decisions_made += 1
            
            # Notify callback
            if self._on_decision and decision.decision_type != DecisionType.NO_ACTION:
                self._on_decision(decision)
            
            # Update recent decisions
            self.state.recent_decisions.append(decision)
            if len(self.state.recent_decisions) > 100:
                self.state.recent_decisions = self.state.recent_decisions[-100:]
            
        except Exception as e:
            logger.error(f"Error in agent cycle: {e}", exc_info=True)
            errors.append(str(e))
            # Create minimal snapshots for error case
            market = self.observer.get_market_snapshot()
            performance = self.observer.get_performance_snapshot()
            decision = None
        
        # Complete cycle
        cycle_end = datetime.now()
        self.state.cycles_completed += 1
        self.state.last_cycle_at = cycle_end
        
        result = CycleResult(
            cycle_number=self.state.cycles_completed,
            started_at=cycle_start,
            completed_at=cycle_end,
            duration_ms=(cycle_end - cycle_start).total_seconds() * 1000,
            market_snapshot=market,
            performance_snapshot=performance,
            patterns_matched=len(matched_patterns) if 'matched_patterns' in dir() else 0,
            recommendations_generated=len(recommendations) if 'recommendations' in dir() else 0,
            decision=decision if 'decision' in dir() else None,
            decision_executed=decision.executed if ('decision' in dir() and decision) else False,
            errors=errors,
        )
        
        if self._on_cycle_complete:
            self._on_cycle_complete(result)
        
        logger.debug(
            f"Cycle {self.state.cycles_completed} completed in {result.duration_ms:.0f}ms"
        )
    
    def _merge_decisions(self, d1: Decision, d2: Decision) -> Decision:
        """Merge two decisions, preferring higher confidence/priority."""
        # Emergency stops always take priority
        if d1.decision_type == DecisionType.EMERGENCY_STOP:
            return d1
        if d2.decision_type == DecisionType.EMERGENCY_STOP:
            return d2
        
        # No action is lowest priority
        if d1.decision_type == DecisionType.NO_ACTION:
            return d2
        if d2.decision_type == DecisionType.NO_ACTION:
            return d1
        
        # Higher confidence wins
        if d1.confidence >= d2.confidence:
            return d1
        return d2
    
    async def run_single_cycle(self) -> CycleResult:
        """
        Run a single cycle and return the result.
        
        Useful for testing or manual triggering.
        """
        cycle_start = datetime.now()
        
        # Observe
        market, positions, performance = self.observer.get_full_context()
        
        # Analyze
        observations = self.analyzer.analyze_market_conditions(market, performance)
        matched_patterns = self.analyzer.match_patterns(market, performance)
        recommendations = self.analyzer.get_active_recommendations()
        risk_assessment = self.analyzer.assess_risk(market, positions, performance)
        
        # Decide
        decision = self.analyzer.generate_decision(
            market, positions, performance,
            observations, matched_patterns, recommendations, risk_assessment
        )
        
        # Execute (if not dry run)
        executed = False
        if not self.config.dry_run and decision.decision_type != DecisionType.NO_ACTION:
            decision = self.executor.execute(decision)
            executed = decision.executed
        
        cycle_end = datetime.now()
        
        return CycleResult(
            cycle_number=self.state.cycles_completed + 1,
            started_at=cycle_start,
            completed_at=cycle_end,
            duration_ms=(cycle_end - cycle_start).total_seconds() * 1000,
            market_snapshot=market,
            performance_snapshot=performance,
            patterns_matched=len(matched_patterns),
            recommendations_generated=len(recommendations),
            decision=decision,
            decision_executed=executed,
            errors=[],
        )
    
    def get_state(self) -> AgentState:
        """Get current agent state."""
        return self.state
    
    def get_status(self) -> dict:
        """Get agent status as a dictionary."""
        return {
            "agent_id": self.state.agent_id,
            "is_running": self.state.is_running,
            "is_paused": self.state.is_paused,
            "mode": self.state.mode.value,
            "cycles_completed": self.state.cycles_completed,
            "decisions_made": self.state.decisions_made,
            "decisions_executed": self.state.decisions_executed,
            "parameter_changes_today": self.state.parameter_changes_today,
            "emergency_stop_active": self.state.emergency_stop_active,
            "current_regime": self.state.current_regime.value,
            "last_cycle_at": self.state.last_cycle_at.isoformat() if self.state.last_cycle_at else None,
            "started_at": self.state.started_at.isoformat(),
        }
    
    def trigger_emergency_stop(self, reason: str = "Manual trigger"):
        """Manually trigger an emergency stop."""
        logger.warning(f"Manual emergency stop triggered: {reason}")
        
        decision = Decision(
            decision_type=DecisionType.EMERGENCY_STOP,
            action="HALT_TRADING",
            confidence=1.0,
            reasoning=f"Manual emergency stop: {reason}",
        )
        
        self.executor.execute(decision)
        self.state.emergency_stop_active = True
        self.state.emergency_stop_reason = reason
        self.state.trading_enabled = False
    
    def clear_emergency_stop(self, reason: str = "Manual clear"):
        """Clear emergency stop and resume trading."""
        if not self.state.emergency_stop_active:
            return
        
        logger.info(f"Clearing emergency stop: {reason}")
        
        decision = Decision(
            decision_type=DecisionType.RESUME_TRADING,
            action="RESUME",
            confidence=1.0,
            reasoning=f"Emergency stop cleared: {reason}",
        )
        
        self.executor.execute(decision)
        self.state.emergency_stop_active = False
        self.state.emergency_stop_reason = None
        self.state.trading_enabled = True


async def run_agent(config: Optional[AgentConfig] = None):
    """
    Run the adaptive agent (main entry point for async context).
    """
    agent = AdaptiveAgent(config)
    
    try:
        await agent.start()
        
        # Keep running until interrupted
        while agent.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await agent.stop()

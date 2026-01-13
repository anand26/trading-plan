"""
Executor Component - Action Execution and Audit Logging

Executes decisions by updating parameters, managing positions,
and logging all actions for audit and learning purposes.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4
import pyodbc

from .config import AgentConfig
from .models import Decision, DecisionType, Alert


logger = logging.getLogger(__name__)


class Executor:
    """
    Executes agent decisions and logs all actions.
    
    Responsibilities:
    - Execute parameter updates
    - Trigger trading actions via MCP
    - Log all decisions for audit
    - Send notifications
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._conn: Optional[pyodbc.Connection] = None
        self._execution_count_today = 0
        self._last_reset_date: Optional[datetime] = None
    
    def _get_connection(self) -> pyodbc.Connection:
        """Get or create database connection."""
        if self._conn is None or not self._is_connection_alive():
            self._conn = pyodbc.connect(
                self.config.database.connection_string,
                autocommit=True
            )
        return self._conn
    
    def _is_connection_alive(self) -> bool:
        """Check if the connection is still alive."""
        try:
            if self._conn is None:
                return False
            cursor = self._conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False
    
    def _reset_daily_counter(self):
        """Reset the daily execution counter if needed."""
        today = datetime.now().date()
        if self._last_reset_date != today:
            self._execution_count_today = 0
            self._last_reset_date = today
    
    def can_execute(self, decision: Decision) -> tuple[bool, str]:
        """
        Check if a decision can be executed.
        
        Returns:
            Tuple of (can_execute: bool, reason: str)
        """
        self._reset_daily_counter()
        
        # Always allow emergency stops
        if decision.decision_type == DecisionType.EMERGENCY_STOP:
            return True, "Emergency actions always allowed"
        
        # Check if in dry run mode
        if self.config.dry_run:
            return False, "Dry run mode - execution disabled"
        
        # Check confidence threshold
        if decision.confidence < self.config.thresholds.min_confidence_to_act:
            return False, f"Confidence {decision.confidence:.2f} below threshold {self.config.thresholds.min_confidence_to_act}"
        
        # Check daily limit for parameter changes
        if decision.decision_type == DecisionType.PARAMETER_ADJUSTMENT:
            if self._execution_count_today >= self.config.thresholds.max_daily_parameter_changes:
                return False, f"Daily parameter change limit ({self.config.thresholds.max_daily_parameter_changes}) reached"
        
        # No action decisions don't need execution
        if decision.decision_type == DecisionType.NO_ACTION:
            return False, "No action required"
        
        return True, "OK"
    
    def execute(self, decision: Decision) -> Decision:
        """
        Execute a decision and return the updated decision.
        
        Args:
            decision: The decision to execute.
            
        Returns:
            Updated Decision with execution results.
        """
        can_exec, reason = self.can_execute(decision)
        
        if not can_exec:
            decision.execution_result = f"Skipped: {reason}"
            self._log_decision(decision)
            return decision
        
        try:
            decision.decision_id = str(uuid4())
            
            if decision.decision_type == DecisionType.EMERGENCY_STOP:
                self._execute_emergency_stop(decision)
            elif decision.decision_type == DecisionType.PARAMETER_ADJUSTMENT:
                self._execute_parameter_adjustment(decision)
            elif decision.decision_type == DecisionType.RISK_SCALING:
                self._execute_risk_scaling(decision)
            elif decision.decision_type == DecisionType.REGIME_ADAPTATION:
                self._execute_regime_adaptation(decision)
            elif decision.decision_type == DecisionType.RESUME_TRADING:
                self._execute_resume_trading(decision)
            
            decision.executed = True
            decision.executed_at = datetime.now()
            decision.execution_result = "Success"
            
            if decision.decision_type == DecisionType.PARAMETER_ADJUSTMENT:
                self._execution_count_today += 1
            
        except Exception as e:
            logger.error(f"Error executing decision: {e}")
            decision.executed = False
            decision.execution_result = f"Error: {str(e)}"
        
        # Log the decision
        self._log_decision(decision)
        
        # Send notification if enabled
        if self.config.notifications.enabled:
            self._send_notification(decision)
        
        return decision
    
    def _execute_emergency_stop(self, decision: Decision):
        """Execute an emergency stop."""
        logger.critical(f"EMERGENCY STOP: {decision.reasoning}")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Update strategy parameters to halt trading
        cursor.execute("""
            UPDATE StrategyParameters
            SET Value = '0',
                UpdatedAt = GETDATE(),
                UpdatedBy = 'AdaptiveAgent'
            WHERE Name = 'TradingEnabled'
        """)
        
        # Record the emergency stop
        cursor.execute("""
            INSERT INTO AgentActions (
                ActionId, ActionType, Description, Executed, 
                ExecutedAt, Confidence, Reasoning
            ) VALUES (?, 'EMERGENCY_STOP', ?, 1, GETDATE(), ?, ?)
        """, (
            decision.decision_id,
            decision.action,
            decision.confidence,
            decision.reasoning,
        ))
        
        cursor.close()
    
    def _execute_parameter_adjustment(self, decision: Decision):
        """Execute a parameter adjustment."""
        if not decision.parameter_name:
            raise ValueError("Parameter name required for parameter adjustment")
        
        logger.info(
            f"Adjusting parameter {decision.parameter_name}: "
            f"{decision.old_value} -> {decision.new_value}"
        )
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Update the parameter
        cursor.execute("""
            MERGE StrategyParameters AS target
            USING (SELECT ? AS Name, ? AS Value) AS source
            ON target.Name = source.Name
            WHEN MATCHED THEN
                UPDATE SET 
                    Value = source.Value,
                    PreviousValue = target.Value,
                    UpdatedAt = GETDATE(),
                    UpdatedBy = 'AdaptiveAgent'
            WHEN NOT MATCHED THEN
                INSERT (Name, Value, UpdatedAt, UpdatedBy)
                VALUES (source.Name, source.Value, GETDATE(), 'AdaptiveAgent');
        """, (
            decision.parameter_name,
            str(decision.new_value),
        ))
        
        # Record the action
        cursor.execute("""
            INSERT INTO AgentActions (
                ActionId, ActionType, ParameterName, OldValue, NewValue,
                Executed, ExecutedAt, Confidence, Reasoning, PatternIds
            ) VALUES (?, 'PARAMETER_ADJUSTMENT', ?, ?, ?, 1, GETDATE(), ?, ?, ?)
        """, (
            decision.decision_id,
            decision.parameter_name,
            str(decision.old_value),
            str(decision.new_value),
            decision.confidence,
            decision.reasoning,
            json.dumps(decision.supporting_patterns),
        ))
        
        # Mark recommendation as applied if applicable
        if decision.action == "APPLY_RECOMMENDATION" and decision.supporting_patterns:
            for pattern_id in decision.supporting_patterns:
                cursor.execute("""
                    EXEC sp_ApplyRecommendation @PatternId = ?
                """, (pattern_id,))
        
        cursor.close()
    
    def _execute_risk_scaling(self, decision: Decision):
        """Execute a risk scaling action."""
        logger.info(f"Risk scaling: {decision.action}")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Scale down position sizes
        if decision.action == "REDUCE_EXPOSURE":
            cursor.execute("""
                UPDATE StrategyParameters
                SET Value = CAST(CAST(Value AS FLOAT) * 0.75 AS VARCHAR),
                    PreviousValue = Value,
                    UpdatedAt = GETDATE(),
                    UpdatedBy = 'AdaptiveAgent'
                WHERE Name IN ('MaxPositionSize', 'ScalpSize')
            """)
        
        # Record the action
        cursor.execute("""
            INSERT INTO AgentActions (
                ActionId, ActionType, Description, Executed, 
                ExecutedAt, Confidence, Reasoning
            ) VALUES (?, 'RISK_SCALING', ?, 1, GETDATE(), ?, ?)
        """, (
            decision.decision_id,
            decision.action,
            decision.confidence,
            decision.reasoning,
        ))
        
        cursor.close()
    
    def _execute_regime_adaptation(self, decision: Decision):
        """Execute a regime adaptation action."""
        logger.info(f"Regime adaptation: {decision.action}")
        
        # This would typically update regime-specific parameters
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO AgentActions (
                ActionId, ActionType, Description, Executed, 
                ExecutedAt, Confidence, Reasoning
            ) VALUES (?, 'REGIME_ADAPTATION', ?, 1, GETDATE(), ?, ?)
        """, (
            decision.decision_id,
            decision.action,
            decision.confidence,
            decision.reasoning,
        ))
        
        cursor.close()
    
    def _execute_resume_trading(self, decision: Decision):
        """Execute a resume trading action."""
        logger.info("Resuming trading operations")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Re-enable trading
        cursor.execute("""
            UPDATE StrategyParameters
            SET Value = '1',
                UpdatedAt = GETDATE(),
                UpdatedBy = 'AdaptiveAgent'
            WHERE Name = 'TradingEnabled'
        """)
        
        # Record the action
        cursor.execute("""
            INSERT INTO AgentActions (
                ActionId, ActionType, Description, Executed, 
                ExecutedAt, Confidence, Reasoning
            ) VALUES (?, 'RESUME_TRADING', ?, 1, GETDATE(), ?, ?)
        """, (
            decision.decision_id,
            decision.action,
            decision.confidence,
            decision.reasoning,
        ))
        
        cursor.close()
    
    def _log_decision(self, decision: Decision):
        """Log a decision to the database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO AgentDecisions (
                    DecisionId, DecisionType, Action, Confidence,
                    ParameterName, OldValue, NewValue, Reasoning,
                    SupportingPatterns, ContributingFactors,
                    MarketSnapshot, PerformanceSnapshot,
                    Executed, ExecutedAt, ExecutionResult,
                    CreatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                decision.decision_id or str(uuid4()),
                decision.decision_type.value,
                decision.action,
                decision.confidence,
                decision.parameter_name,
                str(decision.old_value) if decision.old_value else None,
                str(decision.new_value) if decision.new_value else None,
                decision.reasoning,
                json.dumps(decision.supporting_patterns),
                json.dumps(decision.contributing_factors),
                decision.market_snapshot.model_dump_json() if decision.market_snapshot else None,
                decision.performance_snapshot.model_dump_json() if decision.performance_snapshot else None,
                decision.executed,
                decision.executed_at,
                decision.execution_result,
            ))
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Error logging decision: {e}")
    
    def _send_notification(self, decision: Decision):
        """Send notification about a decision."""
        if decision.decision_type == DecisionType.NO_ACTION:
            return
        
        # Check notification settings
        if decision.decision_type == DecisionType.EMERGENCY_STOP:
            if not self.config.notifications.on_emergency_stop:
                return
        elif decision.decision_type == DecisionType.PARAMETER_ADJUSTMENT:
            if not self.config.notifications.on_parameter_change:
                return
        
        alert = Alert(
            severity="critical" if decision.decision_type == DecisionType.EMERGENCY_STOP else "info",
            category=decision.decision_type.value,
            message=f"{decision.action}: {decision.reasoning}",
            related_decision_id=decision.decision_id,
            data={
                "confidence": decision.confidence,
                "parameter": decision.parameter_name,
                "old_value": str(decision.old_value),
                "new_value": str(decision.new_value),
            },
        )
        
        # Send to Slack if configured
        if self.config.notifications.slack_webhook_url:
            self._send_slack_notification(alert)
        
        # Log the alert
        logger.info(f"Alert: [{alert.severity}] {alert.category} - {alert.message}")
    
    def _send_slack_notification(self, alert: Alert):
        """Send notification to Slack."""
        import httpx
        
        try:
            payload = {
                "text": f"*{alert.severity.upper()}* - {alert.category}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{alert.severity.upper()}* - {alert.category}\n{alert.message}"
                        }
                    }
                ]
            }
            
            httpx.post(
                self.config.notifications.slack_webhook_url,
                json=payload,
                timeout=10.0,
            )
        except Exception as e:
            logger.warning(f"Failed to send Slack notification: {e}")
    
    def get_execution_history(self, limit: int = 50) -> list[dict]:
        """
        Get recent execution history.
        
        Returns:
            List of recent agent actions.
        """
        history = []
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT TOP (?)
                    ActionId, ActionType, ParameterName, OldValue, NewValue,
                    Description, Executed, ExecutedAt, Confidence, Reasoning
                FROM AgentActions
                ORDER BY ExecutedAt DESC
            """, (limit,))
            
            for row in cursor.fetchall():
                history.append({
                    "action_id": row[0],
                    "action_type": row[1],
                    "parameter_name": row[2],
                    "old_value": row[3],
                    "new_value": row[4],
                    "description": row[5],
                    "executed": row[6],
                    "executed_at": row[7],
                    "confidence": row[8],
                    "reasoning": row[9],
                })
            
            cursor.close()
            
        except pyodbc.Error as e:
            logger.warning(f"Error getting execution history: {e}")
        
        return history
    
    def close(self):
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

"""
Command-Line Interface for the Adaptive Agent.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from .config import AgentConfig, get_config
from .agent import AdaptiveAgent, run_agent


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def print_status(agent: AdaptiveAgent):
    """Print current agent status."""
    status = agent.get_status()
    
    print("\n" + "="*60)
    print("ADAPTIVE AGENT STATUS")
    print("="*60)
    print(f"Agent ID:        {status['agent_id']}")
    print(f"Mode:            {status['mode'].upper()}")
    print(f"Running:         {'✓' if status['is_running'] else '✗'}")
    print(f"Paused:          {'✓' if status['is_paused'] else '✗'}")
    print(f"Emergency Stop:  {'⚠ ACTIVE' if status['emergency_stop_active'] else '✗'}")
    print("-"*60)
    print(f"Current Regime:  {status['current_regime']}")
    print(f"Cycles:          {status['cycles_completed']}")
    print(f"Decisions Made:  {status['decisions_made']}")
    print(f"Executed:        {status['decisions_executed']}")
    print(f"Param Changes:   {status['parameter_changes_today']} (today)")
    print("-"*60)
    print(f"Started:         {status['started_at']}")
    print(f"Last Cycle:      {status['last_cycle_at'] or 'N/A'}")
    print("="*60 + "\n")


def on_decision(decision):
    """Callback for agent decisions."""
    if decision.decision_type.value == "NO_ACTION":
        return
    
    print(f"\n📊 DECISION: {decision.decision_type.value}")
    print(f"   Action:     {decision.action}")
    print(f"   Confidence: {decision.confidence:.0%}")
    print(f"   Reasoning:  {decision.reasoning}")
    if decision.executed:
        print(f"   ✓ Executed at {decision.executed_at}")
    print()


def on_cycle_complete(result):
    """Callback for cycle completion."""
    if result.decision and result.decision.decision_type.value != "NO_ACTION":
        return  # Already printed by on_decision
    
    # Just print a dot to show we're running
    print(".", end="", flush=True)


async def run_interactive(config: AgentConfig):
    """Run agent in interactive mode."""
    agent = AdaptiveAgent(config)
    agent.on_decision(on_decision)
    agent.on_cycle_complete(on_cycle_complete)
    
    print("\n" + "="*60)
    print("ADAPTIVE TRADING AGENT")
    print("="*60)
    print(f"Mode: {config.mode.upper()}")
    print(f"Dry Run: {config.dry_run}")
    print(f"Cycle Interval: {config.cycle_interval_seconds}s")
    print("="*60)
    print("\nCommands: [s]tatus, [p]ause, [r]esume, [e]mergency, [c]lear, [q]uit\n")
    
    # Start agent
    await agent.start()
    
    # Input loop
    try:
        while True:
            # Non-blocking input check
            await asyncio.sleep(0.1)
            
            # Check for input (simplified - in production use aioconsole)
            # For now, just run until keyboard interrupt
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        await agent.stop()
        print("Agent stopped.")


async def run_single(config: AgentConfig):
    """Run a single agent cycle."""
    agent = AdaptiveAgent(config)
    
    print("Running single cycle...")
    result = await agent.run_single_cycle()
    
    print(f"\nCycle completed in {result.duration_ms:.0f}ms")
    print(f"Patterns matched: {result.patterns_matched}")
    print(f"Recommendations: {result.recommendations_generated}")
    
    if result.decision:
        print(f"\nDecision: {result.decision.decision_type.value}")
        print(f"Action: {result.decision.action}")
        print(f"Confidence: {result.decision.confidence:.0%}")
        print(f"Reasoning: {result.decision.reasoning}")
        print(f"Executed: {result.decision_executed}")
    
    if result.errors:
        print(f"\nErrors: {result.errors}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Adaptive Trading Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in paper mode with default settings
  python -m adaptive_agent run
  
  # Run single cycle in dry-run mode  
  python -m adaptive_agent cycle --dry-run
  
  # Run with custom interval
  python -m adaptive_agent run --interval 30
  
  # Show current status
  python -m adaptive_agent status
        """
    )
    
    parser.add_argument(
        "command",
        choices=["run", "cycle", "status"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode (default: paper)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Cycle interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - no actual execution"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else args.log_level
    setup_logging(log_level)
    
    # Create config
    config = AgentConfig.from_env()
    config.mode = args.mode
    config.cycle_interval_seconds = args.interval
    config.dry_run = args.dry_run
    config.debug = args.debug
    config.log_level = log_level
    
    # Execute command
    if args.command == "run":
        asyncio.run(run_interactive(config))
    
    elif args.command == "cycle":
        asyncio.run(run_single(config))
    
    elif args.command == "status":
        agent = AdaptiveAgent(config)
        print_status(agent)


if __name__ == "__main__":
    main()

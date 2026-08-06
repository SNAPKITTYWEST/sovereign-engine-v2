"""
Sovereign LLM Engine — Unified Entry Point
Part of SOVEREIGN PYTHON LLM ENGINE

Wires all subsystems into a single SovereignEngine class that manages:
  - ToolRegistry + IPC (NativeToolRouter)
  - RoutingPipeline (expert dispatch)
  - ContinuityManager (task state + recovery)
  - WORMLedger (cryptographic append-only log)
  - ReActAgent (reasoning + action loop)
  - ShadowAgent (optional non-blocking observer)
  - PathJail + SSRFGuard (security)

Typical usage::

    import asyncio
    from src.sovereign import SovereignEngine, EngineConfig, run_task

    async def main():
        config = EngineConfig(
            allowed_roots=[Path("/safe/paths")],
            enable_shadow=True,
        )
        engine = SovereignEngine(config)
        result = await engine.run("write python code to sort a list")
        print(result)
        engine.shutdown()

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

# ── Tool subsystem ──────────────────────────────────────────────────────────
from .tools.registry import ToolRegistry
from .tools.loader import load_all_tools
from .tools.ipc_router import NativeToolRouter

# ── Routing pipeline ────────────────────────────────────────────────────────
from .routing.pipeline import RoutingPipeline

# ── Continuity + State ──────────────────────────────────────────────────────
from .continuity.manager import ContinuityManager

# ── Core subsystems ────────────────────────────────────────────────────────
from .core.evidence import WORMLedger
from .core.crypto import generate_signing_key
from .core.path_jail import PathJail, SSRFGuard

# ── Agents ─────────────────────────────────────────────────────────────────
from .agents.react import ReActAgent, ReActConfig
from .agents.shadow import ShadowAgent

logger = logging.getLogger("sovereign.engine")


# ---------------------------------------------------------------------------
# EngineConfig — Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class EngineConfig:
    """Configuration for SovereignEngine."""
    allowed_roots: list[Path] = field(default_factory=lambda: [Path.cwd()])
    ledger_path: Path = field(default_factory=lambda: Path("./sovereign.worm"))
    continuity_dir: Path = field(default_factory=lambda: Path.home() / ".sovereign" / "continuity")
    max_steps: int = 15
    enable_shadow: bool = True
    enable_ipc: bool = True
    agent_id: str = "sovereign_main"


# ---------------------------------------------------------------------------
# SovereignEngine — Unified subsystem orchestrator
# ---------------------------------------------------------------------------

class SovereignEngine:
    """
    Unified entry point for Sovereign LLM Engine.

    Wires together:
      - ToolRegistry + NativeToolRouter for IPC
      - WORMLedger for cryptographic audit trail
      - ContinuityManager for task recovery
      - RoutingPipeline for expert dispatch
      - ReActAgent for reasoning/action loop
      - ShadowAgent for optional non-blocking observation
      - PathJail + SSRFGuard for security boundaries
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        """Initialize all subsystems."""
        self.config = config or EngineConfig()
        self._logger = logging.getLogger(f"sovereign.engine.{self.config.agent_id}")

        # Security
        self.path_jail = PathJail(roots=self.config.allowed_roots)
        self.ssrf_guard = SSRFGuard()
        self.signing_key = generate_signing_key()

        # Evidence ledger
        self.ledger = WORMLedger(str(self.config.ledger_path), self.signing_key)

        # Tools
        self.registry = ToolRegistry()
        load_all_tools(self.registry)
        self.ipc = NativeToolRouter(self.registry) if self.config.enable_ipc else None

        # State + continuity
        self.continuity = ContinuityManager(str(self.config.continuity_dir))

        # Routing
        self.routing = RoutingPipeline(registry=self.registry)

        # Agents
        react_config = ReActConfig(max_steps=self.config.max_steps)
        self.agent = ReActAgent(
            agent_id=self.config.agent_id,
            config=react_config,
            registry=self.registry,
            ledger=self.ledger,
        )
        self.shadow = ShadowAgent() if self.config.enable_shadow else None

        self._logger.info("SovereignEngine initialized")

    async def run(self, task: str) -> str:
        """
        Execute a task: route → dispatch → ReActAgent loop → return result.

        Args:
            task: Natural-language task description.

        Returns:
            Task result as string.
        """
        self._logger.info("Starting task: %s", task[:100])

        # Create task record in continuity
        task_id = await self.continuity.create_task(task)
        self._logger.debug("Task ID: %s", task_id)

        try:
            # Route to appropriate experts
            dispatch_result = await self.routing.route(task, {})

            # Run ReActAgent loop
            result = await self.agent.run(task, context={"task_id": task_id})

            # Seal in ledger
            await self.ledger.append({
                "task_id": task_id,
                "task": task,
                "result": result,
                "dispatch": str(dispatch_result),
            })

            # Update continuity
            await self.continuity.mark_complete(task_id, result)

            return result
        except Exception as e:
            self._logger.exception("Task failed: %s", task_id)
            await self.continuity.mark_failed(task_id, str(e))
            raise

    async def run_stream(self, task: str) -> AsyncIterator[str]:
        """
        Execute a task with streaming output.

        Args:
            task: Natural-language task description.

        Yields:
            Partial result chunks as strings.
        """
        self._logger.info("Starting streaming task: %s", task[:100])
        task_id = await self.continuity.create_task(task)

        try:
            async for chunk in self.agent.run_stream(task, context={"task_id": task_id}):
                yield chunk
            await self.continuity.mark_complete(task_id, "streaming complete")
        except Exception as e:
            self._logger.exception("Streaming task failed: %s", task_id)
            await self.continuity.mark_failed(task_id, str(e))
            raise

    def shutdown(self) -> None:
        """Clean up resources."""
        self._logger.info("Shutting down")
        if self.ipc:
            self.ipc.shutdown()
        self.continuity.shutdown()
        self._logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

async def run_task(task: str, config: EngineConfig | None = None) -> str:
    """
    Convenience function: create engine, run task, clean up.

    Args:
        task: Natural-language task description.
        config: Optional custom EngineConfig.

    Returns:
        Task result as string.
    """
    engine = SovereignEngine(config or EngineConfig())
    try:
        return await engine.run(task)
    finally:
        engine.shutdown()

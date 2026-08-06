"""
Sovereign LLM Engine — Daemon Package
Part of SOVEREIGN PYTHON LLM ENGINE

Exports:
    PythonDaemon   — asyncio TCP daemon with handler registry
    DaemonTask     — inbound task dataclass
    DaemonHandler  — handler Protocol
    DaemonResponse — outbound response dataclass
    send_task      — client-side coroutine to send one task
    ping_daemon    — client-side health check (PING/PONG)
    Swarm          — parallel swarm coordinator
    SwarmResult    — swarm operation result dataclass
    TaskOutcome    — single task outcome within a swarm
"""

from .python_daemon import (
    DaemonHandler,
    DaemonResponse,
    DaemonTask,
    PythonDaemon,
    ping_daemon,
    send_task,
)
from .swarm import (
    Swarm,
    SwarmResult,
    TaskOutcome,
)

__all__ = [
    # Daemon
    "PythonDaemon",
    "DaemonTask",
    "DaemonHandler",
    "DaemonResponse",
    "send_task",
    "ping_daemon",
    # Swarm
    "Swarm",
    "SwarmResult",
    "TaskOutcome",
]

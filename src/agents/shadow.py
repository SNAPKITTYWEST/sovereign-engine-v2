"""
Sovereign LLM Engine — Shadow Agent
Part of SOVEREIGN PYTHON LLM ENGINE

A non-blocking observer that attaches to any primary agent, intercepts all
tool calls and model invocations, logs everything to the WORM ledger, and
detects anomalies (repeated failures, loops, cost spikes, timeout patterns)
without ever blocking or modifying primary agent execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

from ..core.crypto import generate_signing_key
from ..core.evidence import WORMLedger

logger = logging.getLogger("sovereign.shadow")


# ==========================================
# Anomaly Types
# ==========================================

class AnomalyType(Enum):
    """Classifies detected anomalies during observation."""
    REPEATED_FAILURE = "repeated_failure"
    LOOP_DETECTED = "loop_detected"
    COST_SPIKE = "cost_spike"
    TIMEOUT_PATTERN = "timeout_pattern"


# ==========================================
# Event Types
# ==========================================

@dataclass
class ShadowEvent:
    """
    Event emitted by the shadow agent.

    Attributes:
        event_type: Category string, e.g. "tool_call", "model_invoke", "anomaly".
        primary_agent_id: ID of the primary agent being observed.
        data: Arbitrary payload dict.
        timestamp: UTC ISO 8601 timestamp.
        anomaly_type: Set when event_type is "anomaly".
        suggestion: Optional alternative suggestion (stored, never forced).
    """
    event_type: str
    primary_agent_id: str
    data: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    anomaly_type: AnomalyType | None = None
    suggestion: str | None = None


# ==========================================
# Anomaly Detection State
# ==========================================

@dataclass
class _AnomalyState:
    """Internal sliding-window state for anomaly detection."""
    tool_failures: deque[tuple[str, float]]  # (tool_name, timestamp)
    tool_invocations: deque[tuple[str, float]]  # (tool_name, timestamp)
    model_costs: deque[tuple[float, float]]  # (cost_usd, timestamp)
    timeout_events: deque[float]  # timestamps
    # Loop detection: last N tool sequences
    recent_sequences: deque[tuple[str, ...]]

    def __init__(self) -> None:
        self.tool_failures = deque(maxlen=200)
        self.tool_invocations = deque(maxlen=500)
        self.model_costs = deque(maxlen=100)
        self.timeout_events = deque(maxlen=100)
        self.recent_sequences = deque(maxlen=20)
        self._current_sequence: list[str] = []

    def record_tool_invocation(self, tool_name: str) -> None:
        self.tool_invocations.append((tool_name, time.monotonic()))
        self._current_sequence.append(tool_name)
        # Seal sequences of length 3 for loop detection
        if len(self._current_sequence) >= 3:
            seq = tuple(self._current_sequence[-3:])
            self.recent_sequences.append(seq)

    def record_tool_failure(self, tool_name: str) -> None:
        self.tool_failures.append((tool_name, time.monotonic()))

    def record_cost(self, cost_usd: float) -> None:
        self.model_costs.append((cost_usd, time.monotonic()))

    def record_timeout(self) -> None:
        self.timeout_events.append(time.monotonic())

    def count_recent_failures(self, tool_name: str, window_s: float = 60.0) -> int:
        now = time.monotonic()
        return sum(
            1 for name, ts in self.tool_failures
            if name == tool_name and (now - ts) <= window_s
        )

    def count_recent_timeouts(self, window_s: float = 120.0) -> int:
        now = time.monotonic()
        return sum(1 for ts in self.timeout_events if (now - ts) <= window_s)

    def recent_cost_window(self, window_s: float = 300.0) -> float:
        now = time.monotonic()
        return sum(c for c, ts in self.model_costs if (now - ts) <= window_s)

    def detect_loop(self, repeat_threshold: int = 3) -> tuple[bool, str]:
        """
        Detect repeated identical tool sequences.
        Returns (is_loop, description).
        """
        if len(self.recent_sequences) < repeat_threshold:
            return False, ""
        last = self.recent_sequences[-1]
        count = sum(1 for seq in self.recent_sequences if seq == last)
        if count >= repeat_threshold:
            return True, f"Sequence {last} repeated {count} times"
        return False, ""


# ==========================================
# Shadow Agent
# ==========================================

class ShadowAgent:
    """
    Non-blocking observer that silently monitors a primary agent.

    Usage:
        shadow = ShadowAgent(
            agent_id="shadow-01",
            ledger_path=Path("/tmp/shadow_ledger.jsonl"),
        )
        shadow.attach("primary-agent-42")

        # In primary agent code (fire-and-forget, never awaited in critical path):
        shadow.observe_tool_call("web_search", {"query": "..."})
        shadow.observe_model_invoke("claude-3-5-sonnet", tokens_in=100, tokens_out=50, cost_usd=0.001)
        shadow.observe_tool_result("web_search", success=True, result={"hits": 3})

        events = await shadow.get_events()
        shadow.detach()

    The shadow NEVER blocks primary agent execution. All operations are either
    synchronous fire-and-forget (put_nowait on an internal queue) or return
    immediately.
    """

    # Anomaly thresholds (tunable)
    FAILURE_THRESHOLD = 3        # same tool failures within 60s
    LOOP_REPEAT_THRESHOLD = 3    # same sequence repeated N times
    COST_SPIKE_USD = 1.0         # USD within 5-minute window
    TIMEOUT_THRESHOLD = 3        # timeouts within 2 minutes

    def __init__(
        self,
        agent_id: str,
        ledger_path: Path | None = None,
        event_queue_size: int = 1000,
    ) -> None:
        self._agent_id = agent_id
        self._primary_agent_id: str | None = None
        self._attached = False

        # WORM ledger (optional; if no path, use a temp file)
        if ledger_path is None:
            ledger_path = Path(f"/tmp/shadow_{agent_id}.jsonl")
        signing_key = generate_signing_key()
        self._ledger = WORMLedger(ledger_path, signing_key)

        # Async event queue for consumers
        self._event_queue: asyncio.Queue[ShadowEvent] = asyncio.Queue(
            maxsize=event_queue_size
        )

        # Anomaly state
        self._anomaly_state = _AnomalyState()

        # Suggestion store: list of (tool_name, suggestion) pairs
        self._suggestions: list[tuple[str, str]] = []

        logger.info("ShadowAgent '%s' created.", agent_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def attach(self, primary_agent_id: str) -> None:
        """
        Attach the shadow to a primary agent.

        Must be called before any observe_* methods.
        Idempotent if already attached to the same agent.
        """
        if self._attached and self._primary_agent_id == primary_agent_id:
            return
        if self._attached:
            logger.warning(
                "ShadowAgent '%s' detaching from '%s' to attach to '%s'.",
                self._agent_id, self._primary_agent_id, primary_agent_id,
            )
        self._primary_agent_id = primary_agent_id
        self._attached = True
        self._emit(ShadowEvent(
            event_type="shadow_attached",
            primary_agent_id=primary_agent_id,
            data={"shadow_id": self._agent_id},
        ))
        logger.info(
            "ShadowAgent '%s' attached to primary agent '%s'.",
            self._agent_id, primary_agent_id,
        )

    def detach(self) -> None:
        """Detach from the primary agent. Subsequent observe_* calls are no-ops."""
        if not self._attached:
            return
        self._emit(ShadowEvent(
            event_type="shadow_detached",
            primary_agent_id=self._primary_agent_id or "",
            data={"shadow_id": self._agent_id},
        ))
        self._attached = False
        logger.info(
            "ShadowAgent '%s' detached from '%s'.",
            self._agent_id, self._primary_agent_id,
        )
        self._primary_agent_id = None

    # ------------------------------------------------------------------
    # Observation entry points (fire-and-forget, never block caller)
    # ------------------------------------------------------------------

    def observe_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        """
        Record that the primary agent is about to call `tool_name`.
        Does not block. Safe to call from sync or async context.
        """
        if not self._attached:
            return
        self._anomaly_state.record_tool_invocation(tool_name)
        event = ShadowEvent(
            event_type="tool_call",
            primary_agent_id=self._primary_agent_id or "",
            data={"tool": tool_name, "arguments": arguments},
        )
        self._emit(event)
        self._check_loop_anomaly()

    def observe_tool_result(
        self,
        tool_name: str,
        success: bool,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        """
        Record the result of a tool invocation.
        Triggers failure/timeout anomaly detection.
        """
        if not self._attached:
            return
        if not success:
            self._anomaly_state.record_tool_failure(tool_name)
            if error and "timeout" in error.lower():
                self._anomaly_state.record_timeout()
        event = ShadowEvent(
            event_type="tool_result",
            primary_agent_id=self._primary_agent_id or "",
            data={
                "tool": tool_name,
                "success": success,
                "result": result,
                "error": error,
            },
        )
        self._emit(event)
        self._check_failure_anomaly(tool_name)
        self._check_timeout_anomaly()

    def observe_model_invoke(
        self,
        model_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
    ) -> None:
        """
        Record a model invocation with token and cost metadata.
        Triggers cost-spike anomaly detection.
        """
        if not self._attached:
            return
        self._anomaly_state.record_cost(cost_usd)
        event = ShadowEvent(
            event_type="model_invoke",
            primary_agent_id=self._primary_agent_id or "",
            data={
                "model": model_id,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
            },
        )
        self._emit(event)
        self._check_cost_anomaly()

    def observe_custom(self, event_type: str, data: dict[str, Any]) -> None:
        """Record a custom event for extensibility."""
        if not self._attached:
            return
        event = ShadowEvent(
            event_type=event_type,
            primary_agent_id=self._primary_agent_id or "",
            data=data,
        )
        self._emit(event)

    # ------------------------------------------------------------------
    # Suggestions (stored, never forced)
    # ------------------------------------------------------------------

    def add_suggestion(self, tool_name: str, suggestion: str) -> None:
        """
        Store an alternative suggestion for a tool invocation.

        Suggestions are never injected into the primary agent;
        they are available for post-hoc review via get_suggestions().
        """
        self._suggestions.append((tool_name, suggestion))
        event = ShadowEvent(
            event_type="suggestion_stored",
            primary_agent_id=self._primary_agent_id or "",
            data={"tool": tool_name, "suggestion": suggestion},
            suggestion=suggestion,
        )
        self._emit(event)

    def get_suggestions(self) -> list[tuple[str, str]]:
        """Return all stored (tool_name, suggestion) pairs."""
        return list(self._suggestions)

    # ------------------------------------------------------------------
    # Event consumption
    # ------------------------------------------------------------------

    async def get_events(
        self,
        max_events: int = 100,
        drain_timeout: float = 0.1,
    ) -> list[ShadowEvent]:
        """
        Drain up to `max_events` events from the internal queue.

        Non-blocking beyond `drain_timeout` seconds; returns whatever
        is available. Does not wait for new events.
        """
        collected: list[ShadowEvent] = []
        deadline = time.monotonic() + drain_timeout
        while len(collected) < max_events:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=remaining
                )
                collected.append(event)
            except asyncio.TimeoutError:
                break
        return collected

    def get_events_nowait(self) -> list[ShadowEvent]:
        """
        Drain all currently available events without blocking.
        Returns immediately.
        """
        events: list[ShadowEvent] = []
        while True:
            try:
                events.append(self._event_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, event: ShadowEvent) -> None:
        """
        Emit an event to both the WORM ledger and the async queue.
        Uses put_nowait so this never blocks the caller.
        """
        # WORM ledger (synchronous I/O — acceptable for non-critical observer path)
        try:
            raw = json.dumps({
                "event_type": event.event_type,
                "primary_agent_id": event.primary_agent_id,
                "data": event.data,
                "timestamp": event.timestamp,
                "anomaly_type": event.anomaly_type.value if event.anomaly_type else None,
                "suggestion": event.suggestion,
            }, default=str)
            self._ledger.append(
                event_type=event.event_type,
                data=raw.encode(),
                metadata={
                    "primary_agent_id": event.primary_agent_id,
                    "shadow_id": self._agent_id,
                },
            )
        except Exception as exc:
            # NEVER let ledger I/O affect primary agent
            logger.debug("Shadow ledger write error (suppressed): %s", exc)

        # Queue
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event to make room (FIFO eviction)
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except Exception:
                pass

    def _emit_anomaly(
        self,
        anomaly_type: AnomalyType,
        description: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        event = ShadowEvent(
            event_type="anomaly",
            primary_agent_id=self._primary_agent_id or "",
            data={
                "anomaly_type": anomaly_type.value,
                "description": description,
                **(extra or {}),
            },
            anomaly_type=anomaly_type,
        )
        self._emit(event)
        logger.warning(
            "ANOMALY detected by ShadowAgent '%s' [%s]: %s",
            self._agent_id, anomaly_type.value, description,
        )

    def _check_failure_anomaly(self, tool_name: str) -> None:
        count = self._anomaly_state.count_recent_failures(tool_name)
        if count >= self.FAILURE_THRESHOLD:
            self._emit_anomaly(
                AnomalyType.REPEATED_FAILURE,
                f"Tool '{tool_name}' failed {count} times in the last 60s",
                {"tool": tool_name, "failure_count": count},
            )

    def _check_loop_anomaly(self) -> None:
        is_loop, description = self._anomaly_state.detect_loop(self.LOOP_REPEAT_THRESHOLD)
        if is_loop:
            self._emit_anomaly(
                AnomalyType.LOOP_DETECTED,
                description,
            )

    def _check_cost_anomaly(self) -> None:
        window_cost = self._anomaly_state.recent_cost_window(300.0)
        if window_cost >= self.COST_SPIKE_USD:
            self._emit_anomaly(
                AnomalyType.COST_SPIKE,
                f"Cost ${window_cost:.4f} in last 5 minutes (threshold ${self.COST_SPIKE_USD})",
                {"window_cost_usd": round(window_cost, 6)},
            )

    def _check_timeout_anomaly(self) -> None:
        count = self._anomaly_state.count_recent_timeouts(120.0)
        if count >= self.TIMEOUT_THRESHOLD:
            self._emit_anomaly(
                AnomalyType.TIMEOUT_PATTERN,
                f"{count} timeouts detected in the last 2 minutes",
                {"timeout_count": count},
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_attached(self) -> bool:
        return self._attached

    @property
    def primary_agent_id(self) -> str | None:
        return self._primary_agent_id

    @property
    def queue_size(self) -> int:
        return self._event_queue.qsize()

    def stats(self) -> dict[str, Any]:
        """Return current internal statistics."""
        return {
            "shadow_id": self._agent_id,
            "attached": self._attached,
            "primary_agent_id": self._primary_agent_id,
            "queue_size": self._event_queue.qsize(),
            "suggestions_stored": len(self._suggestions),
            "recent_failures_60s": {
                name: self._anomaly_state.count_recent_failures(name)
                for name, _ in set(self._anomaly_state.tool_failures)
            },
            "recent_timeouts_120s": self._anomaly_state.count_recent_timeouts(120.0),
            "cost_window_300s_usd": round(
                self._anomaly_state.recent_cost_window(300.0), 6
            ),
        }

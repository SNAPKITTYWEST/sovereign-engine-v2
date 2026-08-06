"""
Sovereign LLM Engine — Parallel Swarm Coordinator
Part of SOVEREIGN PYTHON LLM ENGINE

Coordinates N concurrent async agent tasks using asyncio primitives.
Supports fan_out, map_reduce, and race patterns with configurable
concurrency limits, per-task timeouts, and result aggregation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger("sovereign.swarm")

T = TypeVar("T")
R = TypeVar("R")

# Type aliases for readability
AgentCallable = Callable[..., Coroutine[Any, Any, Any]]
Mapper = Callable[[Any], Coroutine[Any, Any, Any]]
Reducer = Callable[[list[Any]], Coroutine[Any, Any, Any]]


# ==========================================
# Result Types
# ==========================================

@dataclass
class TaskOutcome:
    """Outcome of a single task within a swarm operation."""
    index: int
    success: bool
    value: Any = None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class SwarmResult:
    """
    Aggregated result from a swarm operation.

    Attributes:
        results: Successful results in order of completion (or index for fan_out).
        failures: Failed task outcomes.
        latency_ms: Wall-clock time for the entire swarm operation.
        winner: For race() operations — the first successful result value.
    """
    results: list[Any]
    failures: list[TaskOutcome]
    latency_ms: float
    winner: Any | None = None

    @property
    def success_count(self) -> int:
        return len(self.results)

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def total_count(self) -> int:
        return self.success_count + self.failure_count

    @property
    def all_succeeded(self) -> bool:
        return self.failure_count == 0

    def __repr__(self) -> str:
        return (
            f"SwarmResult(success={self.success_count}, "
            f"failures={self.failure_count}, "
            f"latency_ms={self.latency_ms:.1f})"
        )


# ==========================================
# Internal helpers
# ==========================================

async def _run_with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float | None,
    index: int,
    semaphore: asyncio.Semaphore,
) -> TaskOutcome:
    """
    Run a coroutine under a semaphore and optional timeout.

    Returns a TaskOutcome regardless of success or failure.
    """
    start = time.monotonic()
    async with semaphore:
        try:
            if timeout is not None:
                value = await asyncio.wait_for(coro, timeout=timeout)
            else:
                value = await coro
            latency = (time.monotonic() - start) * 1000.0
            return TaskOutcome(index=index, success=True, value=value, latency_ms=latency)
        except asyncio.TimeoutError:
            latency = (time.monotonic() - start) * 1000.0
            return TaskOutcome(
                index=index,
                success=False,
                error=f"Task {index} timed out after {timeout}s",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000.0
            return TaskOutcome(
                index=index,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=latency,
            )


# ==========================================
# Swarm
# ==========================================

class Swarm:
    """
    Parallel swarm coordinator.

    All operations respect a global concurrency limit (semaphore) and an
    optional per-task timeout. Tasks that exceed the timeout are recorded
    as failures rather than raising exceptions.

    Args:
        concurrency: Maximum number of tasks running simultaneously.
        task_timeout: Per-task timeout in seconds (None = unlimited).
    """

    def __init__(
        self,
        concurrency: int = 16,
        task_timeout: float | None = 60.0,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self._concurrency = concurrency
        self._task_timeout = task_timeout

    # ------------------------------------------------------------------
    # fan_out
    # ------------------------------------------------------------------

    async def fan_out(
        self,
        task: Any,
        agents: list[AgentCallable],
    ) -> SwarmResult:
        """
        Dispatch the same task to every agent concurrently.

        Each agent in `agents` is called as ``agent(task)``.
        Results are returned in the same order as the agent list.
        Failures do not block other agents.

        Returns:
            SwarmResult with results indexed to match agent positions.
        """
        if not agents:
            return SwarmResult(results=[], failures=[], latency_ms=0.0)

        semaphore = asyncio.Semaphore(self._concurrency)
        wall_start = time.monotonic()

        coros = [
            _run_with_timeout(agent(task), self._task_timeout, idx, semaphore)
            for idx, agent in enumerate(agents)
        ]
        outcomes: list[TaskOutcome] = await asyncio.gather(*coros)

        wall_ms = (time.monotonic() - wall_start) * 1000.0

        # Preserve original index order for results
        ordered_results: list[Any] = [None] * len(agents)
        failures: list[TaskOutcome] = []

        for outcome in outcomes:
            if outcome.success:
                ordered_results[outcome.index] = outcome.value
            else:
                failures.append(outcome)
                logger.warning(
                    "fan_out agent[%d] failed: %s", outcome.index, outcome.error
                )

        # Remove None slots for failed agents so callers get a clean list
        success_results = [
            ordered_results[i]
            for i in range(len(agents))
            if outcomes[i].success
        ]

        return SwarmResult(
            results=success_results,
            failures=failures,
            latency_ms=wall_ms,
        )

    # ------------------------------------------------------------------
    # map_reduce
    # ------------------------------------------------------------------

    async def map_reduce(
        self,
        items: list[Any],
        mapper: Mapper,
        reducer: Reducer,
    ) -> SwarmResult:
        """
        Map items through an async mapper concurrently, then reduce.

        Each item in `items` is passed to ``mapper(item)`` concurrently.
        Successful mapped values are collected and passed to ``reducer(values)``.
        The reducer result is the single entry in SwarmResult.results.

        Failures in individual map tasks are recorded; the reducer only
        receives successfully mapped values. If all maps fail, the reducer
        is not called and SwarmResult.results is empty.

        Returns:
            SwarmResult where results[0] is the reducer output (if any map succeeded).
        """
        if not items:
            reduced = await reducer([])
            return SwarmResult(results=[reduced], failures=[], latency_ms=0.0)

        semaphore = asyncio.Semaphore(self._concurrency)
        wall_start = time.monotonic()

        map_coros = [
            _run_with_timeout(mapper(item), self._task_timeout, idx, semaphore)
            for idx, item in enumerate(items)
        ]
        map_outcomes: list[TaskOutcome] = await asyncio.gather(*map_coros)

        mapped_values: list[Any] = []
        failures: list[TaskOutcome] = []

        for outcome in map_outcomes:
            if outcome.success:
                mapped_values.append(outcome.value)
            else:
                failures.append(outcome)
                logger.warning(
                    "map_reduce mapper[%d] failed: %s", outcome.index, outcome.error
                )

        results: list[Any] = []
        if mapped_values:
            try:
                reduced_value = await reducer(mapped_values)
                results = [reduced_value]
            except Exception as exc:
                logger.exception("map_reduce reducer failed: %s", exc)
                failures.append(
                    TaskOutcome(
                        index=-1,
                        success=False,
                        error=f"Reducer {type(exc).__name__}: {exc}",
                    )
                )

        wall_ms = (time.monotonic() - wall_start) * 1000.0
        return SwarmResult(results=results, failures=failures, latency_ms=wall_ms)

    # ------------------------------------------------------------------
    # race
    # ------------------------------------------------------------------

    async def race(
        self,
        tasks: list[Coroutine[Any, Any, Any]],
    ) -> SwarmResult:
        """
        Run tasks concurrently and return the first successful result.

        All remaining tasks are cancelled once a winner is found.
        If all tasks fail, SwarmResult.winner is None and all failures
        are recorded.

        Returns:
            SwarmResult with winner set to the first successful value.
            results contains only the winning value (or empty if all failed).
        """
        if not tasks:
            return SwarmResult(results=[], failures=[], latency_ms=0.0, winner=None)

        semaphore = asyncio.Semaphore(self._concurrency)
        wall_start = time.monotonic()

        # Wrap each coroutine in a task
        loop = asyncio.get_running_loop()
        pending: set[asyncio.Task[TaskOutcome]] = set()

        for idx, coro in enumerate(tasks):
            t = loop.create_task(
                _run_with_timeout(coro, self._task_timeout, idx, semaphore)
            )
            pending.add(t)

        winner: Any | None = None
        winner_found = False
        failures: list[TaskOutcome] = []

        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for finished in done:
                outcome: TaskOutcome = finished.result()
                if outcome.success and not winner_found:
                    winner = outcome.value
                    winner_found = True
                    logger.debug(
                        "race winner: task[%d] in %.1fms",
                        outcome.index,
                        outcome.latency_ms,
                    )
                    # Cancel remaining tasks
                    for remaining in pending:
                        remaining.cancel()
                    # Drain cancelled tasks
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    pending = set()
                    break
                elif not outcome.success:
                    failures.append(outcome)

        wall_ms = (time.monotonic() - wall_start) * 1000.0

        if winner_found:
            return SwarmResult(
                results=[winner],
                failures=failures,
                latency_ms=wall_ms,
                winner=winner,
            )
        else:
            return SwarmResult(
                results=[],
                failures=failures,
                latency_ms=wall_ms,
                winner=None,
            )

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    async def batch(
        self,
        coros: list[Coroutine[Any, Any, Any]],
    ) -> SwarmResult:
        """
        Run an arbitrary list of coroutines concurrently with the swarm
        concurrency and timeout settings. Results are in completion order.

        This is a lower-level primitive used internally; fan_out and
        map_reduce are preferred for agent patterns.
        """
        if not coros:
            return SwarmResult(results=[], failures=[], latency_ms=0.0)

        semaphore = asyncio.Semaphore(self._concurrency)
        wall_start = time.monotonic()

        wrapped = [
            _run_with_timeout(coro, self._task_timeout, idx, semaphore)
            for idx, coro in enumerate(coros)
        ]
        outcomes: list[TaskOutcome] = await asyncio.gather(*wrapped)

        results = [o.value for o in outcomes if o.success]
        failures = [o for o in outcomes if not o.success]
        wall_ms = (time.monotonic() - wall_start) * 1000.0

        return SwarmResult(results=results, failures=failures, latency_ms=wall_ms)

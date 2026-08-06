"""
Supervisor Agent with Tool-Lookup Orchestration
Part of SOVEREIGN PYTHON LLM ENGINE

Orchestrates sub-agents by:
1. Breaking a high-level task into SubTasks via model planning.
2. Assigning the best tool to each SubTask via ToolLookupRegistry.
3. Executing each subtask (delegating to a callable or simulating).
4. Collecting and returning results.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .lookup import ToolCheckout, ToolLookupRegistry, ToolQuery
from .registry import RiskClass


# ==========================================
# SubTask
# ==========================================

@dataclass
class SubTask:
    """
    A single unit of work within a larger plan.

    Attributes:
        id: Unique task identifier (auto-generated if not provided).
        description: Human-readable description of what must be done.
        required_capability: Natural-language description of the tool
            capability needed to complete this subtask.
        assigned_tool: tool_id of the checked-out tool (None until assigned).
        status: Lifecycle state:
            "pending"  — not yet assigned.
            "assigned" — tool checked out, ready to execute.
            "done"     — executed successfully.
            "failed"   — execution raised an exception.
        result: Output produced by execution; None until done.
    """
    description: str
    required_capability: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    assigned_tool: str | None = None
    status: str = "pending"
    result: dict[str, Any] | None = None


# ==========================================
# Model provider protocol (minimal duck-typing)
# ==========================================

class ModelProvider:
    """
    Minimal interface for a text-generation model.

    Implementations must provide an async ``complete`` method.
    The default stub returns empty completions so that
    SupervisorAgent can be instantiated without a real model.
    """

    async def complete(self, prompt: str) -> str:  # pragma: no cover
        """
        Generate a text completion for the given prompt.

        Args:
            prompt: Instruction / context string.

        Returns:
            Model-generated text.
        """
        return ""


# ==========================================
# SupervisorAgent
# ==========================================

class SupervisorAgent:
    """
    Orchestrator that decomposes tasks and routes them to specialised tools.

    The agent follows a plan → assign → execute loop:

        1. ``plan(task)``      — ask model to decompose task into SubTasks.
        2. ``assign(subtask)`` — find the best tool via ToolLookupRegistry.
        3. ``execute_plan``    — run the full loop and collect results.

    A ``delegate`` helper lets the supervisor hand off individual subtasks
    to sub-agent callables while still managing tool checkout lifecycle.
    """

    # Prompt templates
    _PLAN_PROMPT = (
        "You are a planning assistant. Break the following task into a numbered "
        "list of discrete subtasks. For each subtask provide:\n"
        "  - A short description (one sentence).\n"
        "  - The tool capability required (what kind of tool is needed).\n\n"
        "Output format (repeat for each subtask):\n"
        "SUBTASK: <description>\n"
        "CAPABILITY: <required tool capability>\n\n"
        "Task: {task}\n"
    )

    def __init__(
        self,
        lookup: ToolLookupRegistry,
        model_provider: ModelProvider | None = None,
        agent_id: str | None = None,
        risk_max: RiskClass = RiskClass.REVERSIBLE_REMOTE_WRITE,
        max_parallel_tasks: int = 4,
    ) -> None:
        """
        Initialise the supervisor.

        Args:
            lookup: ToolLookupRegistry used for tool discovery and checkout.
            model_provider: Language model used for planning.  A no-op stub
                is used when None.
            agent_id: Stable identifier for this supervisor instance.
                Auto-generated if not provided.
            risk_max: Hard ceiling on the risk class of tools this agent
                may check out.
            max_parallel_tasks: Maximum subtasks to execute concurrently.
        """
        self._lookup = lookup
        self._model = model_provider or ModelProvider()
        self.agent_id = agent_id or f"supervisor-{uuid.uuid4().hex[:8]}"
        self._risk_max = risk_max
        self._max_parallel = max_parallel_tasks

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    async def plan(self, task: str) -> list[SubTask]:
        """
        Decompose a high-level task into SubTasks using the model.

        The model is prompted to produce a structured list of subtasks.
        The response is parsed line by line; any subtask whose description
        or capability cannot be extracted is silently skipped.

        Falls back to a single pass-through SubTask when the model
        returns an empty or unparseable response.

        Args:
            task: Natural-language task description.

        Returns:
            Ordered list of SubTask objects with status "pending".
        """
        prompt = self._PLAN_PROMPT.format(task=task)
        raw_response = await self._model.complete(prompt)
        subtasks = self._parse_plan(raw_response, task)
        return subtasks

    def _parse_plan(self, response: str, original_task: str) -> list[SubTask]:
        """
        Parse model response into SubTask objects.

        Expects lines of the form:
            SUBTASK: <description>
            CAPABILITY: <capability>

        Args:
            response: Raw model text.
            original_task: Used as fallback when parsing yields nothing.

        Returns:
            List of SubTask objects.
        """
        subtasks: list[SubTask] = []
        pending_desc: str | None = None
        pending_cap: str | None = None

        for line in response.splitlines():
            line = line.strip()
            if line.upper().startswith("SUBTASK:"):
                # Flush any complete pending pair
                if pending_desc and pending_cap:
                    subtasks.append(
                        SubTask(
                            description=pending_desc,
                            required_capability=pending_cap,
                        )
                    )
                pending_desc = line[len("SUBTASK:"):].strip()
                pending_cap = None
            elif line.upper().startswith("CAPABILITY:"):
                pending_cap = line[len("CAPABILITY:"):].strip()

        # Flush final pair
        if pending_desc and pending_cap:
            subtasks.append(
                SubTask(
                    description=pending_desc,
                    required_capability=pending_cap,
                )
            )

        # Fallback: treat the whole task as one subtask
        if not subtasks:
            subtasks.append(
                SubTask(
                    description=original_task,
                    required_capability=original_task,
                )
            )

        return subtasks

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    async def assign(self, subtask: SubTask) -> ToolCheckout:
        """
        Find and check out the best tool for a subtask.

        Uses ``ToolLookupRegistry.search`` to rank tools by keyword
        relevance, respecting the supervisor's risk ceiling.  The
        highest-scored tool is checked out and the subtask is marked
        "assigned".

        Args:
            subtask: The subtask to assign a tool to.

        Returns:
            ToolCheckout for the assigned tool.

        Raises:
            RuntimeError: If no matching tool is found.
        """
        query = ToolQuery(
            query=subtask.required_capability,
            agent_id=self.agent_id,
            risk_max=self._risk_max,
            top_k=1,
        )
        result = self._lookup.search(query)

        if not result.tools:
            subtask.status = "failed"
            subtask.result = {
                "error": f"No tool found for capability: {subtask.required_capability!r}"
            }
            raise RuntimeError(
                f"No tool found for subtask {subtask.id!r}: "
                f"{subtask.required_capability!r}"
            )

        best_tool = result.tools[0]
        checkout = self._lookup.checkout(self.agent_id, best_tool.tool_id)
        subtask.assigned_tool = best_tool.tool_id
        subtask.status = "assigned"
        return checkout

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_subtask(
        self,
        subtask: SubTask,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a single assigned subtask using its checked-out tool.

        Calls the tool handler with ``inputs`` (defaults to empty dict).
        Records the tool use and marks the subtask done or failed.

        Args:
            subtask: The assigned subtask to execute.
            inputs: Input parameters forwarded to the tool handler.

        Returns:
            Tool execution result dict.

        Raises:
            RuntimeError: If the subtask is not in "assigned" state.
        """
        if subtask.status != "assigned":
            raise RuntimeError(
                f"Cannot execute subtask {subtask.id!r} in state {subtask.status!r}. "
                "Call assign() first."
            )

        tool_id = subtask.assigned_tool
        if tool_id is None:
            raise RuntimeError(f"Subtask {subtask.id!r} has no assigned_tool.")

        tool_def = self._lookup._registry.get(tool_id)
        if tool_def is None:
            subtask.status = "failed"
            subtask.result = {"error": f"Tool {tool_id!r} disappeared from registry."}
            return subtask.result

        try:
            output = await tool_def.handler(inputs or {})
            self._lookup.record_use(self.agent_id, tool_id)
            subtask.status = "done"
            subtask.result = output
            return output
        except Exception as exc:
            subtask.status = "failed"
            subtask.result = {"error": str(exc), "tool_id": tool_id}
            raise

    async def execute_plan(
        self,
        task: str,
        inputs_by_subtask: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Full plan → assign → execute → collect loop.

        Steps:
        1. Call ``plan`` to decompose the task.
        2. Assign a tool to each subtask (sequential, fast).
        3. Execute all subtasks concurrently (up to ``max_parallel_tasks``).
        4. Return a summary with per-subtask results.

        Assignment failures do not abort the loop; the subtask is marked
        "failed" and execution is skipped for it.

        Args:
            task: High-level task description.
            inputs_by_subtask: Optional map of subtask_id -> input params.
                Subtasks not in the map receive an empty input dict.

        Returns:
            Summary dict with keys:
                "task", "subtasks" (list of serialised SubTask results),
                "success_count", "failure_count".
        """
        subtasks = await self.plan(task)
        inputs_by_subtask = inputs_by_subtask or {}

        # Assignment is fast (registry lookup) — do sequentially
        for subtask in subtasks:
            try:
                await self.assign(subtask)
            except RuntimeError:
                # subtask already marked failed inside assign()
                pass

        # Execute assigned subtasks with bounded concurrency
        semaphore = asyncio.Semaphore(self._max_parallel)

        async def _bounded_execute(subtask: SubTask) -> None:
            async with semaphore:
                if subtask.status != "assigned":
                    return
                inputs = inputs_by_subtask.get(subtask.id, {})
                try:
                    await self._execute_subtask(subtask, inputs)
                except Exception:
                    # Error already recorded on subtask.result
                    pass

        await asyncio.gather(*[_bounded_execute(st) for st in subtasks])

        success = sum(1 for st in subtasks if st.status == "done")
        failure = sum(1 for st in subtasks if st.status == "failed")

        return {
            "task": task,
            "subtasks": [
                {
                    "id": st.id,
                    "description": st.description,
                    "required_capability": st.required_capability,
                    "assigned_tool": st.assigned_tool,
                    "status": st.status,
                    "result": st.result,
                }
                for st in subtasks
            ],
            "success_count": success,
            "failure_count": failure,
        }

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    async def delegate(
        self,
        task: str,
        agent_callable: Callable[[str, list[str]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """
        Delegate a task to a sub-agent callable with pre-checked-out tools.

        The supervisor:
        1. Plans the task to determine which tools are needed.
        2. Checks out all required tools.
        3. Passes the task and list of tool_ids to ``agent_callable``.
        4. Checks in all tools after the callable completes (or fails).

        The sub-agent callable signature:
            async def agent(task: str, tool_ids: list[str]) -> dict

        Args:
            task: High-level task description.
            agent_callable: Coroutine function that executes the task.

        Returns:
            Result dict from ``agent_callable``, augmented with
            "delegated_tools" (list of tool_ids that were checked out).
        """
        subtasks = await self.plan(task)
        checked_out_ids: list[str] = []

        for subtask in subtasks:
            try:
                checkout = await self.assign(subtask)
                checked_out_ids.append(checkout.tool_id)
            except RuntimeError:
                pass  # Best-effort; sub-agent must handle missing tools

        try:
            result = await agent_callable(task, checked_out_ids)
        finally:
            for tool_id in checked_out_ids:
                self._lookup.checkin(self.agent_id, tool_id)

        result["delegated_tools"] = checked_out_ids
        return result

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_active_tools(self) -> list[str]:
        """
        Return the tool_ids currently checked out by this supervisor.

        Returns:
            List of tool_id strings.
        """
        return [t.tool_id for t in self._lookup.get_agent_tools(self.agent_id)]

    def release_all(self) -> None:
        """
        Check in all tools and clear the session cache for this supervisor.
        """
        self._lookup.release_agent(self.agent_id)

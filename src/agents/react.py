"""
ReAct Agent Implementation
Part of SOVEREIGN PYTHON LLM ENGINE

ReAct = Reasoning + Acting
Agent loops through: Thought → Action → Observation → Reflection

Continuity layer (Ahmad's four paradigms) is wired into every state
transition so the agent can be paused, resumed, hot-restarted, or
replayed from any step without data loss.
"""

from typing import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from ..models.entities import (
    Message,
    MessageRole,
    AgentStep,
    AgentTrajectory,
    ActionType,
    Task,
    ToolCall,
    ToolResult,
)
from ..models.state_machines import AgentState, AgentStateMachine
from ..engine.rules import should_reflect, should_terminate
from ..engine.transformations import extract_tag_content, parse_tool_call
from ..core.protocols import Model, Tool
from ..core.evidence import WORMLedger, EvidenceRecord
from ..tools.registry import ToolRegistry
from ..tools.approval import ApprovalEngine
from ..continuity.manager import ContinuityManager


@dataclass
class ReActConfig:
    """Configuration for ReAct agent"""
    max_steps: int = 10
    reflection_on_error: bool = True
    log_to_worm: bool = True
    require_approval_for_risky: bool = True
    # Continuity
    continuity_base_dir: Path = Path.home() / ".sovereign" / "continuity"
    enable_continuity: bool = True


class ReActAgent:
    """
    ReAct agent with tool calling and self-reflection.

    Loop:
    1. Thought: Agent reasons about what to do next
    2. Action: Agent calls a tool or provides final answer
    3. Observation: Tool result is observed
    4. Reflection: If error, agent reflects on what went wrong
    5. Repeat until final answer or max steps
    """

    def __init__(
        self,
        model: Model,
        tool_registry: ToolRegistry,
        approval_engine: ApprovalEngine | None = None,
        worm_ledger: WORMLedger | None = None,
        config: ReActConfig | None = None,
        agent_id: str | None = None,
    ):
        self.model = model
        self.tool_registry = tool_registry
        self.approval_engine = approval_engine
        self.worm_ledger = worm_ledger
        self.config = config or ReActConfig()
        self.agent_id = agent_id or f"react_{id(self)}"

        self.state_machine = AgentStateMachine()

        # Continuity layer — all four paradigms
        self.continuity: ContinuityManager | None = None
        if self.config.enable_continuity:
            try:
                self.continuity = ContinuityManager(
                    base_dir=self.config.continuity_base_dir,
                    agent_id=self.agent_id,
                )
                # Resume from env if this is a hot-restarted daemon
                if self.continuity.was_restarted:
                    self._step_offset = self.continuity.get_step()
                else:
                    self._step_offset = 0
            except Exception:
                self.continuity = None
                self._step_offset = 0
        else:
            self._step_offset = 0

    async def run(
        self,
        task: Task,
        initial_context: str | None = None
    ) -> str:
        """
        Run ReAct loop to completion.

        Args:
            task: Task to execute
            initial_context: Optional context to seed the agent

        Returns:
            Final answer string
        """
        # Initialize state
        state = self.state_machine.initial_state(
            query=task.description,
            task_id=task.id,
            max_steps=self.config.max_steps
        )

        if initial_context:
            state = self.state_machine.add_context(state, initial_context)

        # Continuity: mark agent as active across all four backends
        if self.continuity:
            self.continuity.set_states({'THINKING'})
            self.continuity.set_step(self._step_offset)
            self.continuity.advance_op(f"START:{task.description[:64]}")

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Initialize conversation
        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=system_prompt,
                created_at=datetime.utcnow()
            ),
            Message(
                role=MessageRole.USER,
                content=task.description,
                created_at=datetime.utcnow()
            )
        ]

        # Main loop
        while not should_terminate(state):
            # Generate next step
            response = await self.model.generate(
                messages=[msg.model_dump() for msg in messages],
                temperature=0.2,
                max_tokens=2048
            )

            # Parse response
            thought = extract_tag_content(response, "thought") or ""
            action_text = extract_tag_content(response, "action") or ""
            final_answer = extract_tag_content(response, "final") or ""

            # Log thought
            if thought:
                state = self.state_machine.add_thought(state, thought)
                if self.continuity:
                    self.continuity.transition('THINKING', 'THINKING')
                    self.continuity.advance_op(f"THINK:{thought[:48]}")

            # Check for final answer
            if final_answer:
                state = self.state_machine.set_final_answer(state, final_answer)

                if self.continuity:
                    self.continuity.transition('THINKING', 'DONE')
                    self.continuity.advance_op('FINAL_ANSWER')

                if self.config.log_to_worm and self.worm_ledger:
                    await self._log_to_worm(task, state, "completed")

                break

            # Execute action
            if action_text:
                if self.continuity:
                    self.continuity.transition('THINKING', 'ACTING')
                    self.continuity.advance_op(f"ACT:{action_text[:48]}")

                observation = await self._execute_action(action_text, state)

                # Add observation to state
                state = self.state_machine.add_observation(state, observation)

                if self.continuity:
                    self.continuity.transition('ACTING', 'OBSERVING')
                    self.continuity.advance_op(f"OBS:{observation[:48]}")

                # Add to messages
                messages.append(Message(
                    role=MessageRole.ASSISTANT,
                    content=response,
                    created_at=datetime.utcnow()
                ))
                messages.append(Message(
                    role=MessageRole.TOOL,
                    content=observation,
                    created_at=datetime.utcnow()
                ))

                # Check if reflection needed
                if should_reflect(state):
                    if self.continuity:
                        self.continuity.transition('OBSERVING', 'REFLECTING')
                        self.continuity.advance_op('REFLECT')

                    reflection = await self._reflect(messages, state)
                    messages.append(Message(
                        role=MessageRole.ASSISTANT,
                        content=f"<reflection>{reflection}</reflection>",
                        created_at=datetime.utcnow()
                    ))

                    if self.continuity:
                        self.continuity.transition('REFLECTING', 'THINKING')
            else:
                # No action found, add response to messages
                messages.append(Message(
                    role=MessageRole.ASSISTANT,
                    content=response,
                    created_at=datetime.utcnow()
                ))

            # Increment step — syncs across all four continuity backends
            state = self.state_machine.increment_step(state)
            if self.continuity:
                self.continuity.increment_step()

        # Return final answer or error
        final_answer = state.get("final_answer")
        if final_answer:
            if self.continuity:
                self.continuity.set_states({'DONE'})
            return final_answer

        # Max steps reached
        error = "Agent reached maximum steps without providing final answer"
        if self.continuity:
            self.continuity.set_states({'ERROR'})
            self.continuity.advance_op('MAX_STEPS_REACHED')

        if self.config.log_to_worm and self.worm_ledger:
            await self._log_to_worm(task, state, "max_steps_reached")

        return error

    async def run_stream(
        self,
        task: Task,
        initial_context: str | None = None
    ) -> AsyncIterator[AgentStep]:
        """
        Run ReAct loop with streaming steps.

        Yields:
            AgentStep for each step in the trajectory
        """
        state = self.state_machine.initial_state(
            query=task.description,
            task_id=task.id,
            max_steps=self.config.max_steps
        )

        if initial_context:
            state = self.state_machine.add_context(state, initial_context)

        system_prompt = self._build_system_prompt()
        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=system_prompt,
                created_at=datetime.utcnow()
            ),
            Message(
                role=MessageRole.USER,
                content=task.description,
                created_at=datetime.utcnow()
            )
        ]

        while not should_terminate(state):
            response = await self.model.generate(
                messages=[msg.model_dump() for msg in messages],
                temperature=0.2,
                max_tokens=2048
            )

            thought = extract_tag_content(response, "thought") or ""
            action_text = extract_tag_content(response, "action") or ""
            final_answer = extract_tag_content(response, "final") or ""

            if thought:
                state = self.state_machine.add_thought(state, thought)
                yield AgentStep(
                    step_number=state["step_count"],
                    action_type=ActionType.THOUGHT,
                    content=thought,
                    timestamp=datetime.utcnow()
                )

            if final_answer:
                state = self.state_machine.set_final_answer(state, final_answer)
                yield AgentStep(
                    step_number=state["step_count"],
                    action_type=ActionType.FINAL_ANSWER,
                    content=final_answer,
                    timestamp=datetime.utcnow()
                )
                break

            if action_text:
                observation = await self._execute_action(action_text, state)
                state = self.state_machine.add_observation(state, observation)

                yield AgentStep(
                    step_number=state["step_count"],
                    action_type=ActionType.EXECUTE_TOOL,
                    content=action_text,
                    observation=observation,
                    timestamp=datetime.utcnow()
                )

                messages.append(Message(
                    role=MessageRole.ASSISTANT,
                    content=response,
                    created_at=datetime.utcnow()
                ))
                messages.append(Message(
                    role=MessageRole.TOOL,
                    content=observation,
                    created_at=datetime.utcnow()
                ))

                if should_reflect(state):
                    reflection = await self._reflect(messages, state)
                    messages.append(Message(
                        role=MessageRole.ASSISTANT,
                        content=f"<reflection>{reflection}</reflection>",
                        created_at=datetime.utcnow()
                    ))

                    yield AgentStep(
                        step_number=state["step_count"],
                        action_type=ActionType.REFLECT,
                        content=reflection,
                        timestamp=datetime.utcnow()
                    )

            state = self.state_machine.increment_step(state)

    async def _execute_action(
        self,
        action_text: str,
        state: AgentState
    ) -> str:
        """
        Execute tool call from action text.

        Args:
            action_text: Raw action text (may contain tool call)
            state: Current agent state

        Returns:
            Observation string
        """
        # Try to parse tool call
        tool_call = parse_tool_call(action_text)

        if not tool_call:
            return "ERROR: Could not parse tool call from action"

        tool_name, arguments = tool_call

        # Get tool from registry
        tool_def = self.tool_registry.get(tool_name)
        if not tool_def:
            return f"ERROR: Tool not found: {tool_name}"

        # Check approval policy
        if self.approval_engine and self.config.require_approval_for_risky:
            approved, reason = await self.approval_engine.check_approval(
                tool_def,
                arguments,
                actor="react_agent"
            )

            if not approved:
                return f"ERROR: Tool execution denied: {reason}"

        # Execute tool
        import time
        t0 = time.monotonic()
        try:
            result = await tool_def.handler(**arguments)
            latency_ms = (time.monotonic() - t0) * 1000

            # Log to WORM ledger
            if self.config.log_to_worm and self.worm_ledger:
                await self.worm_ledger.append(
                    "tool_execution",
                    f"{tool_name} step={state['step_count']}".encode()
                )

            # Advance continuity seed chain with tool result
            if self.continuity:
                self.continuity.advance_op(f"TOOL_OK:{tool_name}")

            return str(result)

        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            error_msg = f"ERROR: Tool execution failed: {str(e)}"

            if self.config.log_to_worm and self.worm_ledger:
                await self.worm_ledger.append(
                    "tool_execution_error",
                    f"{tool_name} error={str(e)[:64]}".encode()
                )

            if self.continuity:
                self.continuity.advance_op(f"TOOL_ERR:{tool_name}")

            return error_msg

    async def _reflect(
        self,
        messages: list[Message],
        state: AgentState
    ) -> str:
        """
        Generate reflection on error.

        Args:
            messages: Conversation history
            state: Current agent state

        Returns:
            Reflection string
        """
        reflection_prompt = """
The previous action failed or returned an error. Reflect on:
1. What went wrong?
2. What should be tried differently?
3. Is there an alternative approach?

Provide a concise reflection (2-3 sentences).
"""

        messages_with_prompt = messages + [
            Message(
                role=MessageRole.USER,
                content=reflection_prompt,
                created_at=datetime.utcnow()
            )
        ]

        reflection = await self.model.generate(
            messages=[msg.model_dump() for msg in messages_with_prompt],
            temperature=0.3,
            max_tokens=256
        )

        return reflection.strip()

    def _build_system_prompt(self) -> str:
        """Build system prompt with tool descriptions"""

        # Get available tools
        tools = self.tool_registry.list_all()

        tool_descriptions = []
        for tool in tools[:20]:  # Limit to 20 tools to avoid context overflow
            tool_descriptions.append(
                f"- {tool.tool_id}: {tool.description}"
            )

        tools_text = "\n".join(tool_descriptions)

        return f"""You are a ReAct agent that solves tasks by reasoning and taking actions.

Available Tools:
{tools_text}

Response Format:
<thought>
Your reasoning about what to do next
</thought>

<action>
<tool_call name="tool_name">
{{"param1": "value1", "param2": "value2"}}
</tool_call>
</action>

OR

<final>
Your final answer when the task is complete
</final>

Rules:
1. Think before acting
2. Use tools to gather information and take actions
3. Reflect on errors and try alternative approaches
4. Provide a final answer when you have sufficient information

Begin!"""

    async def _log_to_worm(
        self,
        task: Task,
        state: AgentState,
        status: str
    ) -> None:
        """Log agent execution to WORM ledger"""
        if not self.worm_ledger:
            return

        await self.worm_ledger.append({
            "event": "react_agent_execution",
            "task_id": task.task_id,
            "task_description": task.description,
            "status": status,
            "steps": state["step_count"],
            "final_answer": state.get("final_answer"),
            "timestamp": datetime.utcnow().isoformat()
        })

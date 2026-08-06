"""
Layer 2: State Machines
Part of SOVEREIGN PYTHON LLM ENGINE

Deterministic state machines for agent workflows.
All transitions are pure functions (no side effects).
"""

from typing import TypedDict, Literal, Callable
from dataclasses import dataclass
from enum import Enum

from .entities import ActionType, TaskStatus, MessageRole


# ==========================================
# Agent State Machine
# ==========================================

class AgentState(TypedDict, total=False):
    """
    State for agent reasoning loop.

    TypedDict provides typed state without requiring Pydantic overhead.
    All fields are optional (total=False) to support incremental state building.
    """
    # Input
    query: str
    task_id: str

    # Routing
    router_decision: str | None
    router_confidence: float | None
    router_reasoning: str | None

    # Retrieval
    retrieved_context: str | None
    retrieval_source: str | None

    # Agent loop
    step_count: int
    max_steps: int
    current_thought: str | None
    current_action: str | None
    current_action_input: str | None
    current_observation: str | None
    current_reflection: str | None

    # Termination
    final_answer: str | None
    error: str | None
    terminated: bool

    # Metadata
    quantum_encoded: bool
    moe_activated_experts: list[int]


class AgentStateMachine:
    """
    State machine for agent execution.

    Defines valid transitions and ensures state consistency.
    """

    @staticmethod
    def initial_state(query: str, task_id: str, max_steps: int = 10) -> AgentState:
        """Create initial state"""
        return AgentState(
            query=query,
            task_id=task_id,
            step_count=0,
            max_steps=max_steps,
            terminated=False,
            quantum_encoded=False,
            moe_activated_experts=[]
        )

    @staticmethod
    def route_query(state: AgentState, decision: str, confidence: float, reasoning: str) -> AgentState:
        """Transition: Add routing decision"""
        return {
            **state,
            "router_decision": decision,
            "router_confidence": confidence,
            "router_reasoning": reasoning
        }

    @staticmethod
    def add_context(state: AgentState, context: str, source: str) -> AgentState:
        """Transition: Add retrieved context"""
        return {
            **state,
            "retrieved_context": context,
            "retrieval_source": source
        }

    @staticmethod
    def add_thought(state: AgentState, thought: str) -> AgentState:
        """Transition: Add agent thought"""
        return {
            **state,
            "current_thought": thought
        }

    @staticmethod
    def add_action(
        state: AgentState,
        action: str,
        action_input: str | None = None
    ) -> AgentState:
        """Transition: Add agent action"""
        return {
            **state,
            "current_action": action,
            "current_action_input": action_input
        }

    @staticmethod
    def add_observation(state: AgentState, observation: str) -> AgentState:
        """Transition: Add observation from action execution"""
        return {
            **state,
            "current_observation": observation
        }

    @staticmethod
    def add_reflection(state: AgentState, reflection: str) -> AgentState:
        """Transition: Add self-reflection"""
        return {
            **state,
            "current_reflection": reflection
        }

    @staticmethod
    def increment_step(state: AgentState) -> AgentState:
        """Transition: Increment step counter"""
        return {
            **state,
            "step_count": state["step_count"] + 1
        }

    @staticmethod
    def set_final_answer(state: AgentState, answer: str) -> AgentState:
        """Transition: Set final answer and terminate"""
        return {
            **state,
            "final_answer": answer,
            "terminated": True
        }

    @staticmethod
    def set_error(state: AgentState, error: str) -> AgentState:
        """Transition: Set error and terminate"""
        return {
            **state,
            "error": error,
            "terminated": True
        }

    @staticmethod
    def mark_quantum_encoded(state: AgentState) -> AgentState:
        """Transition: Mark state as using quantum encoding"""
        return {
            **state,
            "quantum_encoded": True
        }

    @staticmethod
    def add_activated_expert(state: AgentState, expert_id: int) -> AgentState:
        """Transition: Record activated expert"""
        experts = state.get("moe_activated_experts", [])
        return {
            **state,
            "moe_activated_experts": experts + [expert_id]
        }


# ==========================================
# Decision Rules (Pure Functions)
# ==========================================

def should_reflect(state: AgentState) -> bool:
    """Rule: Should agent reflect on last step?"""
    error_in_state = state.get("error") is not None
    error_in_observation = "ERROR" in state.get("current_observation", "")
    failure_in_observation = "FAILED" in state.get("current_observation", "")

    return error_in_state or error_in_observation or failure_in_observation


def should_terminate(state: AgentState) -> bool:
    """Rule: Should agent loop terminate?"""
    has_answer = state.get("final_answer") is not None
    has_error = state.get("error") is not None
    max_steps_reached = state["step_count"] >= state["max_steps"]
    already_terminated = state.get("terminated", False)

    return has_answer or has_error or max_steps_reached or already_terminated


def should_route(state: AgentState) -> bool:
    """Rule: Should query be routed?"""
    no_decision_yet = state.get("router_decision") is None
    no_context_yet = state.get("retrieved_context") is None

    return no_decision_yet and no_context_yet


def should_retrieve(state: AgentState) -> bool:
    """Rule: Should retrieval be executed?"""
    has_decision = state.get("router_decision") is not None
    no_context_yet = state.get("retrieved_context") is None

    return has_decision and no_context_yet


# ==========================================
# Task State Machine
# ==========================================

class TaskStateMachine:
    """
    State machine for task lifecycle.
    """

    @staticmethod
    def can_start(current_status: TaskStatus) -> bool:
        """Check if task can be started"""
        return current_status == TaskStatus.PENDING

    @staticmethod
    def can_complete(current_status: TaskStatus) -> bool:
        """Check if task can be completed"""
        return current_status == TaskStatus.IN_PROGRESS

    @staticmethod
    def can_fail(current_status: TaskStatus) -> bool:
        """Check if task can fail"""
        return current_status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

    @staticmethod
    def can_cancel(current_status: TaskStatus) -> bool:
        """Check if task can be cancelled"""
        return current_status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

    @staticmethod
    def transition(current_status: TaskStatus, new_status: TaskStatus) -> TaskStatus:
        """
        Attempt state transition.

        Raises:
            ValueError: If transition is invalid
        """
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
            TaskStatus.COMPLETED: set(),  # Terminal state
            TaskStatus.FAILED: set(),     # Terminal state
            TaskStatus.CANCELLED: set()   # Terminal state
        }

        if new_status not in valid_transitions[current_status]:
            raise ValueError(
                f"Invalid transition: {current_status} -> {new_status}"
            )

        return new_status


# ==========================================
# MCTS Node State Machine
# ==========================================

class MCTSNodePhase(str, Enum):
    """Phases in MCTS algorithm"""
    SELECTION = "selection"
    EXPANSION = "expansion"
    EVALUATION = "evaluation"
    BACKPROPAGATION = "backpropagation"


class MCTSState(TypedDict, total=False):
    """State for MCTS search"""
    phase: str
    current_node_id: str
    root_node_id: str
    iteration: int
    max_iterations: int
    best_node_id: str | None
    best_score: float
    terminated: bool


class MCTSStateMachine:
    """State machine for MCTS search"""

    @staticmethod
    def initial_state(root_node_id: str, max_iterations: int = 15) -> MCTSState:
        """Create initial MCTS state"""
        return MCTSState(
            phase=MCTSNodePhase.SELECTION.value,
            current_node_id=root_node_id,
            root_node_id=root_node_id,
            iteration=0,
            max_iterations=max_iterations,
            best_score=0.0,
            terminated=False
        )

    @staticmethod
    def transition_to_expansion(state: MCTSState, selected_node_id: str) -> MCTSState:
        """Transition: Selection -> Expansion"""
        return {
            **state,
            "phase": MCTSNodePhase.EXPANSION.value,
            "current_node_id": selected_node_id
        }

    @staticmethod
    def transition_to_evaluation(state: MCTSState, expanded_node_id: str) -> MCTSState:
        """Transition: Expansion -> Evaluation"""
        return {
            **state,
            "phase": MCTSNodePhase.EVALUATION.value,
            "current_node_id": expanded_node_id
        }

    @staticmethod
    def transition_to_backpropagation(state: MCTSState, evaluated_score: float) -> MCTSState:
        """Transition: Evaluation -> Backpropagation"""
        return {
            **state,
            "phase": MCTSNodePhase.BACKPROPAGATION.value,
            "best_score": max(state["best_score"], evaluated_score)
        }

    @staticmethod
    def transition_to_selection(state: MCTSState) -> MCTSState:
        """Transition: Backpropagation -> Selection (next iteration)"""
        return {
            **state,
            "phase": MCTSNodePhase.SELECTION.value,
            "iteration": state["iteration"] + 1,
            "current_node_id": state["root_node_id"]
        }

    @staticmethod
    def terminate(state: MCTSState, best_node_id: str) -> MCTSState:
        """Terminate search"""
        return {
            **state,
            "best_node_id": best_node_id,
            "terminated": True
        }


def mcts_should_terminate(state: MCTSState) -> bool:
    """Rule: Should MCTS search terminate?"""
    max_iterations_reached = state["iteration"] >= state["max_iterations"]
    already_terminated = state.get("terminated", False)
    perfect_score = state["best_score"] >= 1.0

    return max_iterations_reached or already_terminated or perfect_score


# ==========================================
# Conversation State Machine
# ==========================================

class ConversationState(TypedDict, total=False):
    """State for multi-turn conversation"""
    conversation_id: str
    message_count: int
    last_role: str
    context_used_tokens: int
    max_context_tokens: int
    summary_needed: bool


class ConversationStateMachine:
    """State machine for conversation management"""

    @staticmethod
    def initial_state(conversation_id: str, max_context_tokens: int = 4096) -> ConversationState:
        """Create initial conversation state"""
        return ConversationState(
            conversation_id=conversation_id,
            message_count=0,
            context_used_tokens=0,
            max_context_tokens=max_context_tokens,
            summary_needed=False
        )

    @staticmethod
    def add_message(
        state: ConversationState,
        role: MessageRole,
        token_count: int
    ) -> ConversationState:
        """Add message to conversation"""
        new_token_count = state["context_used_tokens"] + token_count
        summary_needed = new_token_count > (state["max_context_tokens"] * 0.8)

        return {
            **state,
            "message_count": state["message_count"] + 1,
            "last_role": role.value,
            "context_used_tokens": new_token_count,
            "summary_needed": summary_needed
        }

    @staticmethod
    def apply_summary(state: ConversationState, new_token_count: int) -> ConversationState:
        """Apply conversation summary (context compression)"""
        return {
            **state,
            "context_used_tokens": new_token_count,
            "summary_needed": False
        }


def conversation_needs_compression(state: ConversationState) -> bool:
    """Rule: Should conversation be compressed?"""
    return state.get("summary_needed", False)


# ==========================================
# Quantum MoE State
# ==========================================

class QuantumMoEState(TypedDict, total=False):
    """State for quantum MoE layer"""
    token_id: int
    quantum_encoded: bool
    duplicates_created: int
    experts_activated: list[int]
    jordan_blocks_count: int
    gating_entropy: float


class QuantumMoEStateMachine:
    """State machine for quantum MoE operations"""

    @staticmethod
    def initial_state(token_id: int) -> QuantumMoEState:
        """Create initial quantum MoE state"""
        return QuantumMoEState(
            token_id=token_id,
            quantum_encoded=False,
            duplicates_created=0,
            experts_activated=[],
            jordan_blocks_count=0,
            gating_entropy=0.0
        )

    @staticmethod
    def mark_quantum_encoded(state: QuantumMoEState) -> QuantumMoEState:
        """Mark token as quantum encoded"""
        return {
            **state,
            "quantum_encoded": True
        }

    @staticmethod
    def set_duplicates(state: QuantumMoEState, count: int) -> QuantumMoEState:
        """Record number of quantum duplicates created"""
        return {
            **state,
            "duplicates_created": count
        }

    @staticmethod
    def set_activated_experts(state: QuantumMoEState, expert_ids: list[int]) -> QuantumMoEState:
        """Record activated experts"""
        return {
            **state,
            "experts_activated": expert_ids,
            "jordan_blocks_count": len(expert_ids)
        }

    @staticmethod
    def set_gating_entropy(state: QuantumMoEState, entropy: float) -> QuantumMoEState:
        """Record gating entropy"""
        return {
            **state,
            "gating_entropy": entropy
        }


# ==========================================
# State Transition Validator
# ==========================================

@dataclass
class StateTransitionRule:
    """
    Rule for validating state transitions.
    """
    name: str
    precondition: Callable[[AgentState], bool]
    postcondition: Callable[[AgentState], bool]
    transition: Callable[[AgentState], AgentState]


def validate_transition(
    rule: StateTransitionRule,
    state: AgentState
) -> tuple[bool, str | None]:
    """
    Validate state transition against rule.

    Returns:
        (valid, error_message)
    """
    if not rule.precondition(state):
        return False, f"Precondition failed for rule: {rule.name}"

    new_state = rule.transition(state)

    if not rule.postcondition(new_state):
        return False, f"Postcondition failed for rule: {rule.name}"

    return True, None

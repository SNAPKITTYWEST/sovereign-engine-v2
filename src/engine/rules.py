"""
Layer 3: Rule Evaluation
Part of SOVEREIGN PYTHON LLM ENGINE

Deterministic rules for decision-making.
All rules are pure predicates (state -> bool).
"""

from typing import Callable
import re

from ..models.state_machines import AgentState, TaskStatus, MCTSState
from ..models.entities import ActionType, MessageRole


# ==========================================
# Type Aliases
# ==========================================

Rule = Callable[[AgentState], bool]
TaskRule = Callable[[TaskStatus], bool]
MCTSRule = Callable[[MCTSState], bool]


# ==========================================
# Agent Loop Rules
# ==========================================

def should_reflect(state: AgentState) -> bool:
    """
    Rule: Should agent reflect on previous step?

    Triggers:
    - Explicit error in state
    - ERROR keyword in observation
    - FAILED keyword in observation
    - Code execution failure
    """
    # Check for explicit error
    if state.get("error") is not None:
        return True

    # Check observation for error indicators
    observation = state.get("current_observation", "")
    error_keywords = ["ERROR", "FAILED", "Exception", "Traceback"]

    return any(keyword in observation for keyword in error_keywords)


def should_terminate(state: AgentState) -> bool:
    """
    Rule: Should agent loop terminate?

    Terminates when:
    - Final answer is provided
    - Error is set
    - Max steps reached
    - Already terminated flag is set
    """
    has_answer = state.get("final_answer") is not None
    has_error = state.get("error") is not None
    max_steps_reached = state["step_count"] >= state["max_steps"]
    already_terminated = state.get("terminated", False)

    return has_answer or has_error or max_steps_reached or already_terminated


def should_route(state: AgentState) -> bool:
    """
    Rule: Should query be routed to a specific source?

    Routes when:
    - No routing decision has been made yet
    - No context has been retrieved yet
    """
    no_decision = state.get("router_decision") is None
    no_context = state.get("retrieved_context") is None

    return no_decision and no_context


def should_retrieve(state: AgentState) -> bool:
    """
    Rule: Should retrieval be executed?

    Retrieves when:
    - Routing decision exists
    - But context hasn't been retrieved yet
    """
    has_decision = state.get("router_decision") is not None
    no_context = state.get("retrieved_context") is None

    return has_decision and no_context


def should_use_quantum_encoding(state: AgentState) -> bool:
    """
    Rule: Should quantum token encoding be used?

    Uses quantum encoding when:
    - Not already quantum encoded
    - Step count is even (alternating pattern)
    - MoE layer will be used
    """
    not_encoded = not state.get("quantum_encoded", False)
    even_step = state["step_count"] % 2 == 0

    return not_encoded and even_step


def is_code_execution_action(state: AgentState) -> bool:
    """Rule: Is current action a code execution?"""
    action = state.get("current_action")
    return action == ActionType.EXECUTE_CODE.value


def is_tool_execution_action(state: AgentState) -> bool:
    """Rule: Is current action a tool execution?"""
    action = state.get("current_action")
    return action == ActionType.EXECUTE_TOOL.value


def is_reflection_action(state: AgentState) -> bool:
    """Rule: Is current action a reflection?"""
    action = state.get("current_action")
    return action == ActionType.REFLECT.value


def needs_context_compression(state: AgentState) -> bool:
    """
    Rule: Does conversation context need compression?

    Compresses when:
    - Step count > 5 (enough history to summarize)
    - Observation length > 2000 chars (long context)
    """
    enough_steps = state["step_count"] > 5
    observation = state.get("current_observation", "")
    long_observation = len(observation) > 2000

    return enough_steps and long_observation


# ==========================================
# Task Lifecycle Rules
# ==========================================

def can_start_task(status: TaskStatus) -> bool:
    """Rule: Can task be started?"""
    return status == TaskStatus.PENDING


def can_complete_task(status: TaskStatus) -> bool:
    """Rule: Can task be completed?"""
    return status == TaskStatus.IN_PROGRESS


def can_fail_task(status: TaskStatus) -> bool:
    """Rule: Can task fail?"""
    return status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)


def can_cancel_task(status: TaskStatus) -> bool:
    """Rule: Can task be cancelled?"""
    return status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)


def is_task_terminal(status: TaskStatus) -> bool:
    """Rule: Is task in terminal state?"""
    return status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


# ==========================================
# MCTS Search Rules
# ==========================================

def mcts_should_terminate(state: MCTSState) -> bool:
    """
    Rule: Should MCTS search terminate?

    Terminates when:
    - Max iterations reached
    - Perfect score achieved (1.0)
    - Already terminated flag set
    """
    max_iterations = state["iteration"] >= state["max_iterations"]
    perfect_score = state["best_score"] >= 1.0
    already_terminated = state.get("terminated", False)

    return max_iterations or perfect_score or already_terminated


def mcts_should_expand(state: MCTSState, node_visit_count: int) -> bool:
    """
    Rule: Should node be expanded?

    Expands when:
    - Node has been visited at least once
    - OR node is the root
    """
    return node_visit_count > 0 or state["current_node_id"] == state["root_node_id"]


def mcts_is_in_selection_phase(state: MCTSState) -> bool:
    """Rule: Is MCTS in selection phase?"""
    return state["phase"] == "selection"


def mcts_is_in_expansion_phase(state: MCTSState) -> bool:
    """Rule: Is MCTS in expansion phase?"""
    return state["phase"] == "expansion"


def mcts_is_in_evaluation_phase(state: MCTSState) -> bool:
    """Rule: Is MCTS in evaluation phase?"""
    return state["phase"] == "evaluation"


def mcts_is_in_backpropagation_phase(state: MCTSState) -> bool:
    """Rule: Is MCTS in backpropagation phase?"""
    return state["phase"] == "backpropagation"


# ==========================================
# Quantum MoE Rules
# ==========================================

def should_activate_moe(token_count: int, threshold: int = 10) -> bool:
    """
    Rule: Should MoE layer be activated?

    Activates when:
    - Token count exceeds threshold
    """
    return token_count >= threshold


def should_use_top_k_gating(num_experts: int, sparsity_target: float = 0.025) -> bool:
    """
    Rule: Should top-K gating be used?

    Always true for quantum MoE (1000 experts, 2.5% sparsity).
    """
    return num_experts >= 100  # Use sparse gating for large expert counts


def expert_is_activated(expert_id: int, activated_experts: list[int]) -> bool:
    """Rule: Is expert activated?"""
    return expert_id in activated_experts


def jordan_sum_is_valid(weights: list[float], tolerance: float = 1e-6) -> bool:
    """
    Rule: Do Jordan softmax weights sum to -1?

    Validates quantum MoE constraint.
    """
    total = sum(weights)
    return abs(total - (-1.0)) < tolerance


# ==========================================
# Message & Conversation Rules
# ==========================================

def is_system_message(role: MessageRole | str) -> bool:
    """Rule: Is message from system?"""
    if isinstance(role, str):
        return role.lower() == "system"
    return role == MessageRole.SYSTEM


def is_user_message(role: MessageRole | str) -> bool:
    """Rule: Is message from user?"""
    if isinstance(role, str):
        return role.lower() == "user"
    return role == MessageRole.USER


def is_assistant_message(role: MessageRole | str) -> bool:
    """Rule: Is message from assistant?"""
    if isinstance(role, str):
        return role.lower() == "assistant"
    return role == MessageRole.ASSISTANT


def is_tool_message(role: MessageRole | str) -> bool:
    """Rule: Is message from tool?"""
    if isinstance(role, str):
        return role.lower() in ("tool", "ipython")
    return role in (MessageRole.TOOL, MessageRole.IPYTHON)


def conversation_alternates_correctly(messages: list[dict[str, str]]) -> bool:
    """
    Rule: Do messages alternate between user and assistant?

    Checks if conversation follows proper turn-taking.
    """
    if len(messages) < 2:
        return True

    for i in range(len(messages) - 1):
        curr_role = messages[i]["role"]
        next_role = messages[i + 1]["role"]

        # Skip system messages
        if curr_role == "system" or next_role == "system":
            continue

        # User should be followed by assistant, and vice versa
        if curr_role == "user" and next_role != "assistant":
            return False
        if curr_role == "assistant" and next_role not in ("user", "tool"):
            return False

    return True


# ==========================================
# Content Validation Rules
# ==========================================

def contains_code_block(text: str) -> bool:
    """Rule: Does text contain markdown code block?"""
    return bool(re.search(r'```\w*\n', text))


def contains_json(text: str) -> bool:
    """Rule: Does text contain JSON object/array?"""
    import json
    try:
        json.loads(text)
        return True
    except:
        # Try to find JSON-like structure
        return bool(re.search(r'\{[^{}]*\}|\[[^\[\]]*\]', text))


def contains_error_keywords(text: str) -> bool:
    """Rule: Does text contain error keywords?"""
    error_keywords = [
        "error", "exception", "failed", "failure", "traceback",
        "invalid", "incorrect", "wrong", "cannot", "unable"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in error_keywords)


def contains_success_keywords(text: str) -> bool:
    """Rule: Does text contain success keywords?"""
    success_keywords = [
        "success", "successful", "completed", "done", "finished",
        "passed", "correct", "valid", "works"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in success_keywords)


def is_empty_or_whitespace(text: str) -> bool:
    """Rule: Is text empty or whitespace-only?"""
    return not text.strip()


def exceeds_length_limit(text: str, limit: int) -> bool:
    """Rule: Does text exceed length limit?"""
    return len(text) > limit


# ==========================================
# Numeric Validation Rules
# ==========================================

def is_in_range(value: float, min_val: float, max_val: float) -> bool:
    """Rule: Is value in range [min_val, max_val]?"""
    return min_val <= value <= max_val


def is_positive(value: float) -> bool:
    """Rule: Is value positive?"""
    return value > 0


def is_non_negative(value: float) -> bool:
    """Rule: Is value non-negative?"""
    return value >= 0


def is_probability(value: float) -> bool:
    """Rule: Is value a valid probability [0, 1]?"""
    return 0.0 <= value <= 1.0


def is_temperature(value: float) -> bool:
    """Rule: Is value a valid temperature [0, 2]?"""
    return 0.0 <= value <= 2.0


# ==========================================
# Composite Rules (Logical Combinations)
# ==========================================

def all_rules(*rules: Rule) -> Rule:
    """
    Combine rules with AND logic.

    Returns:
        Rule that passes if ALL input rules pass
    """
    def combined_rule(state: AgentState) -> bool:
        return all(rule(state) for rule in rules)
    return combined_rule


def any_rules(*rules: Rule) -> Rule:
    """
    Combine rules with OR logic.

    Returns:
        Rule that passes if ANY input rule passes
    """
    def combined_rule(state: AgentState) -> bool:
        return any(rule(state) for rule in rules)
    return combined_rule


def not_rule(rule: Rule) -> Rule:
    """
    Negate a rule.

    Returns:
        Rule that passes if input rule fails
    """
    def negated_rule(state: AgentState) -> bool:
        return not rule(state)
    return negated_rule


# ==========================================
# Rule Registry
# ==========================================

AGENT_RULES = {
    "should_reflect": should_reflect,
    "should_terminate": should_terminate,
    "should_route": should_route,
    "should_retrieve": should_retrieve,
    "should_use_quantum_encoding": should_use_quantum_encoding,
    "is_code_execution": is_code_execution_action,
    "is_tool_execution": is_tool_execution_action,
    "is_reflection": is_reflection_action,
    "needs_compression": needs_context_compression
}

TASK_RULES = {
    "can_start": can_start_task,
    "can_complete": can_complete_task,
    "can_fail": can_fail_task,
    "can_cancel": can_cancel_task,
    "is_terminal": is_task_terminal
}

MCTS_RULES = {
    "should_terminate": mcts_should_terminate,
    "should_expand": lambda state: mcts_should_expand(state, 1),
    "is_selection": mcts_is_in_selection_phase,
    "is_expansion": mcts_is_in_expansion_phase,
    "is_evaluation": mcts_is_in_evaluation_phase,
    "is_backpropagation": mcts_is_in_backpropagation_phase
}


def get_agent_rule(name: str) -> Rule:
    """Get agent rule by name"""
    if name not in AGENT_RULES:
        raise ValueError(f"Unknown agent rule: {name}")
    return AGENT_RULES[name]


def get_task_rule(name: str) -> TaskRule:
    """Get task rule by name"""
    if name not in TASK_RULES:
        raise ValueError(f"Unknown task rule: {name}")
    return TASK_RULES[name]


def get_mcts_rule(name: str) -> MCTSRule:
    """Get MCTS rule by name"""
    if name not in MCTS_RULES:
        raise ValueError(f"Unknown MCTS rule: {name}")
    return MCTS_RULES[name]

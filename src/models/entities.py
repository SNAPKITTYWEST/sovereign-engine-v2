"""
Layer 2: Domain Entities
Part of SOVEREIGN PYTHON LLM ENGINE

Core domain entities with validation and immutability guarantees.
All entities are Pydantic models with strict type checking.
"""

from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Any
from datetime import datetime

from ..core.types import (
    TaskID, ModelID, ToolID, AgentID, ExpertID,
    Temperature, PositiveInt, UTCTimestamp,
    NonEmptyString, TokenID
)
from ..core.crypto import ContentHash, Signature


# ==========================================
# Message Entities
# ==========================================

class MessageRole(str, Enum):
    """Message roles in conversation"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    IPYTHON = "ipython"  # For tool results in ReAct


class Message(BaseModel):
    """
    Single message in conversation history.

    Immutable once created.
    """
    role: MessageRole
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: UTCTimestamp.now().value)

    class Config:
        frozen = True  # Immutable


class Conversation(BaseModel):
    """
    Complete conversation history.

    Maintains message ordering and provides helper methods.
    """
    messages: list[Message] = Field(default_factory=list)
    conversation_id: str | None = None

    def add_message(self, role: MessageRole, content: str, metadata: dict | None = None) -> None:
        """Add message to conversation"""
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(msg)

    def get_last_message(self) -> Message | None:
        """Get most recent message"""
        return self.messages[-1] if self.messages else None

    def get_messages_by_role(self, role: MessageRole) -> list[Message]:
        """Filter messages by role"""
        return [m for m in self.messages if m.role == role]

    def to_dict_list(self) -> list[dict[str, str]]:
        """Convert to standard format for LLM APIs"""
        return [
            {"role": m.role.value, "content": m.content}
            for m in self.messages
        ]


# ==========================================
# Agent Step Entities
# ==========================================

class ActionType(str, Enum):
    """Agent action types"""
    THOUGHT = "thought"
    EXECUTE_CODE = "execute_code"
    EXECUTE_TOOL = "execute_tool"
    REFLECT = "reflect"
    FINAL_ANSWER = "final_answer"


class AgentStep(BaseModel):
    """
    Single step in agent reasoning loop.

    Represents one iteration of the ReAct/reasoning cycle.
    """
    step_number: int = Field(ge=1)
    thought: str
    action: ActionType
    action_input: str | None = None
    observation: str | None = None
    reflection: str | None = None
    timestamp: datetime = Field(default_factory=lambda: UTCTimestamp.now().value)

    class Config:
        frozen = True


class AgentTrajectory(BaseModel):
    """
    Complete trajectory of agent reasoning.

    Records all steps taken to reach final answer.
    """
    task_id: TaskID
    agent_id: AgentID
    steps: list[AgentStep] = Field(default_factory=list)
    final_answer: str | None = None
    success: bool = False
    error: str | None = None

    def add_step(
        self,
        thought: str,
        action: ActionType,
        action_input: str | None = None,
        observation: str | None = None,
        reflection: str | None = None
    ) -> AgentStep:
        """Add step to trajectory"""
        step = AgentStep(
            step_number=len(self.steps) + 1,
            thought=thought,
            action=action,
            action_input=action_input,
            observation=observation,
            reflection=reflection
        )
        self.steps.append(step)
        return step

    def get_step_count(self) -> int:
        """Get total number of steps"""
        return len(self.steps)


# ==========================================
# Task Entities
# ==========================================

class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """
    Task to be executed by an agent.
    """
    id: TaskID
    description: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: UTCTimestamp.now().value)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    agent_id: AgentID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_in_progress(self, agent_id: AgentID) -> None:
        """Mark task as started"""
        self.status = TaskStatus.IN_PROGRESS
        self.agent_id = agent_id
        self.started_at = UTCTimestamp.now().value

    def mark_completed(self, result: str) -> None:
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = UTCTimestamp.now().value

    def mark_failed(self, error: str) -> None:
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = UTCTimestamp.now().value


# ==========================================
# Tool Execution Entities
# ==========================================

class ToolCall(BaseModel):
    """
    Tool invocation request.
    """
    tool_id: ToolID
    tool_name: str
    parameters: dict[str, Any]
    call_id: str | None = None  # Unique ID for this specific call

    class Config:
        frozen = True


class ToolResult(BaseModel):
    """
    Result of tool execution.
    """
    call_id: str
    tool_name: str
    success: bool
    output: Any
    error: str | None = None
    execution_time_ms: int | None = None

    class Config:
        frozen = True


# ==========================================
# Code Execution Entities
# ==========================================

class CodeExecutionRequest(BaseModel):
    """Request to execute code in sandbox"""
    code: str
    language: str = "python"
    timeout_seconds: float = 10.0
    max_output_bytes: int = 4000


class CodeExecutionResult(BaseModel):
    """Result of code execution"""
    success: bool
    output: str
    exit_code: int
    elapsed_ms: int
    stdout: str | None = None
    stderr: str | None = None

    class Config:
        frozen = True


# ==========================================
# Model Inference Entities
# ==========================================

class InferenceRequest(BaseModel):
    """Request for model inference"""
    model_id: ModelID
    messages: list[Message]
    temperature: Temperature = Field(default_factory=Temperature.standard)
    max_tokens: PositiveInt | None = None
    stream: bool = False
    response_format: dict[str, Any] | None = None  # For structured output
    tools: list[dict[str, Any]] | None = None  # For tool calling


class InferenceResponse(BaseModel):
    """Response from model inference"""
    model_id: ModelID
    content: str
    finish_reason: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: dict[str, int] | None = None  # Token usage stats

    class Config:
        frozen = True


# ==========================================
# Expert & MoE Entities
# ==========================================

class ExpertActivation(BaseModel):
    """
    Record of expert activation in MoE.
    """
    expert_id: ExpertID
    weight: float = Field(ge=-1.0, le=1.0)  # Jordan softmax allows negative
    jordan_eigenvalue: float
    jordan_multiplicity: int

    class Config:
        frozen = True


class MoEGatingOutput(BaseModel):
    """
    Output of MoE gating network.
    """
    selected_experts: list[ExpertActivation]
    gating_entropy: float  # Entropy of routing distribution
    sparsity_ratio: float  # Fraction of experts activated
    quantum_encoded: bool = False  # Whether quantum encoding was used

    class Config:
        frozen = True


# ==========================================
# Retrieval Entities
# ==========================================

class RetrievalSource(str, Enum):
    """Available retrieval sources"""
    VECTOR_DB = "vector_db"
    KNOWLEDGE_BASE = "knowledge_base"
    SQL_DATABASE = "sql_database"
    INTERNET_SEARCH = "internet_search"
    GITHUB = "github"
    WIKIPEDIA = "wikipedia"


class RetrievalRequest(BaseModel):
    """Request to retrieve information"""
    query: str
    source: RetrievalSource | None = None  # If None, router decides
    k: int = Field(default=5, ge=1)  # Number of results


class RetrievalResult(BaseModel):
    """Result of information retrieval"""
    query: str
    source: RetrievalSource
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_time_ms: int | None = None

    class Config:
        frozen = True


# ==========================================
# MCTS Search Entities
# ==========================================

class MCTSNodeState(BaseModel):
    """
    State of a node in MCTS tree.
    """
    node_id: str
    code_state: str  # Current accumulated code
    parent_id: str | None = None
    visit_count: int = 0
    total_value: float = 0.0
    prior_probability: float = 1.0
    is_terminal: bool = False
    terminal_reward: float | None = None

    @property
    def q_value(self) -> float:
        """Mean action value"""
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count


class MCTSSearchResult(BaseModel):
    """Result of MCTS search"""
    best_trajectory: list[str]  # Sequence of code states
    best_score: float
    total_iterations: int
    total_nodes_explored: int
    final_code: str


# ==========================================
# Evidence & Provenance Entities
# ==========================================

class ProvenanceRecord(BaseModel):
    """
    Provenance record for artifact.

    Links artifact to its creation context.
    """
    artifact_hash: ContentHash
    creator: AgentID | str
    created_at: datetime
    source_data_hashes: list[ContentHash] = Field(default_factory=list)
    transformation_steps: list[str] = Field(default_factory=list)
    signature: Signature | None = None

    class Config:
        frozen = True


class AuditTrail(BaseModel):
    """
    Complete audit trail for task execution.
    """
    task_id: TaskID
    events: list[dict[str, Any]] = Field(default_factory=list)
    provenance_records: list[ProvenanceRecord] = Field(default_factory=list)

    def add_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Add event to audit trail"""
        event = {
            "timestamp": UTCTimestamp.now().value.isoformat(),
            "event_type": event_type,
            "data": data
        }
        self.events.append(event)


# ==========================================
# Scanner Entities
# ==========================================

class SymbolInfo(BaseModel):
    """
    Symbols extracted from code file.
    """
    classes: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)

    class Config:
        frozen = True


class FileInfo(BaseModel):
    """
    Information about a scanned file.
    """
    path: str
    extension: str
    size_bytes: int
    symbols: SymbolInfo | None = None
    hash: ContentHash | None = None

    class Config:
        frozen = True


class DependencyEdge(BaseModel):
    """
    Directed edge in dependency graph.
    """
    source: str  # File path
    target: str  # File path
    import_type: str = "import"  # "import", "from", "relative"

    class Config:
        frozen = True


class DependencyGraph(BaseModel):
    """
    Complete dependency graph for codebase.
    """
    nodes: list[str] = Field(default_factory=list)  # File paths
    edges: list[DependencyEdge] = Field(default_factory=list)

    def get_dependencies(self, file_path: str) -> list[str]:
        """Get files this file depends on"""
        return [e.target for e in self.edges if e.source == file_path]

    def get_dependents(self, file_path: str) -> list[str]:
        """Get files that depend on this file"""
        return [e.source for e in self.edges if e.target == file_path]

    def get_importance_score(self, file_path: str) -> int:
        """Get importance score (number of dependents)"""
        return len(self.get_dependents(file_path))

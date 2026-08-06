"""
Layer 1: Protocol Definitions
Part of SOVEREIGN PYTHON LLM ENGINE

Typed protocols for all major system components.
Protocols define contracts without implementation.
"""

from typing import Protocol, AsyncIterator, Any, runtime_checkable
import numpy as np


# ==========================================
# Retrieval Protocols
# ==========================================

@runtime_checkable
class Retriever(Protocol):
    """
    Protocol for all retrieval sources (RAG, search, database, etc.)

    Implementations:
    - WikipediaRetriever
    - GitHubRetriever
    - VectorStoreRetriever
    - SQLRetriever
    """

    async def retrieve(self, query: str) -> str:
        """
        Retrieve relevant content for query.

        Args:
            query: User query string

        Returns:
            Retrieved content (may be concatenated from multiple sources)

        Raises:
            RetrievalError: If retrieval fails
        """
        ...


@runtime_checkable
class BatchRetriever(Protocol):
    """Retriever that supports batch queries"""

    async def retrieve_batch(self, queries: list[str]) -> list[str]:
        """Retrieve content for multiple queries concurrently"""
        ...


# ==========================================
# Tool Execution Protocols
# ==========================================

@runtime_checkable
class Tool(Protocol):
    """
    Protocol for executable tools (code execution, API calls, etc.)

    All tools must:
    - Accept structured parameters (dict)
    - Return structured results (dict)
    - Be async
    - Handle errors gracefully
    """

    name: str
    description: str
    parameters_schema: dict[str, Any]  # JSON schema

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute tool with given parameters.

        Args:
            params: Tool parameters (validated against schema)

        Returns:
            Tool execution results

        Raises:
            ToolExecutionError: If execution fails
        """
        ...


@runtime_checkable
class SandboxedTool(Protocol):
    """Tool that runs in isolated sandbox (e.g., code execution)"""

    timeout: float  # Execution timeout in seconds

    async def execute_sandboxed(
        self,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute in isolated environment"""
        ...


# ==========================================
# Model Inference Protocols
# ==========================================

@runtime_checkable
class Model(Protocol):
    """
    Protocol for LLM inference backends.

    Implementations:
    - LlamaAPIBackend
    - OpenAIBackend
    - AnthropicBackend
    - LocalTransformerBackend
    """

    model_id: str

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stream: bool = False
    ) -> str | AsyncIterator[str]:
        """
        Generate completion from messages.

        Args:
            messages: List of {role, content} dicts
            temperature: Sampling temperature [0.0, 2.0]
            max_tokens: Max tokens to generate (None = model default)
            stream: If True, return AsyncIterator of chunks

        Returns:
            Complete response string, or AsyncIterator of chunks if stream=True

        Raises:
            ModelError: If generation fails
        """
        ...


@runtime_checkable
class StructuredOutputModel(Protocol):
    """Model that supports structured output (JSON schema enforcement)"""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any],  # JSON schema
        temperature: float = 0.0
    ) -> dict[str, Any]:
        """
        Generate structured output matching schema.

        Args:
            messages: Conversation history
            response_schema: JSON schema to enforce
            temperature: Sampling temperature

        Returns:
            Validated structured output

        Raises:
            SchemaValidationError: If output doesn't match schema
        """
        ...


@runtime_checkable
class ToolCallingModel(Protocol):
    """Model that supports native tool calling"""

    async def generate_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],  # Tool definitions
        temperature: float = 0.0
    ) -> dict[str, Any]:
        """
        Generate with tool calling support.

        Returns:
            {
                "content": str,
                "tool_calls": [{"name": str, "arguments": dict}]
            }
        """
        ...


# ==========================================
# Storage Protocols
# ==========================================

@runtime_checkable
class KeyValueStore(Protocol):
    """Key-value storage interface"""

    async def get(self, key: str) -> bytes | None:
        """Get value for key, None if not found"""
        ...

    async def put(self, key: str, value: bytes) -> None:
        """Store key-value pair"""
        ...

    async def delete(self, key: str) -> None:
        """Delete key"""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Vector database interface for embeddings"""

    dimension: int  # Embedding dimension

    async def add(
        self,
        vectors: np.ndarray,  # [n, dimension]
        metadata: list[dict[str, Any]]
    ) -> list[str]:
        """
        Add vectors with metadata.

        Returns:
            List of assigned IDs
        """
        ...

    async def search(
        self,
        query_vector: np.ndarray,  # [dimension]
        k: int = 5
    ) -> list[dict[str, Any]]:
        """
        Search for k nearest neighbors.

        Returns:
            List of {id, distance, metadata} dicts
        """
        ...


@runtime_checkable
class TransactionalStore(Protocol):
    """Database with transaction support"""

    async def begin_transaction(self) -> Any:
        """Begin transaction, return transaction handle"""
        ...

    async def commit(self, txn: Any) -> None:
        """Commit transaction"""
        ...

    async def rollback(self, txn: Any) -> None:
        """Rollback transaction"""
        ...


# ==========================================
# Agent Protocols
# ==========================================

@runtime_checkable
class Agent(Protocol):
    """
    Protocol for autonomous agents.

    Implementations:
    - ReActAgent
    - MCTSAgent
    - ReasoningAgent
    """

    agent_id: str
    max_steps: int

    async def run(self, task: str) -> str:
        """
        Execute agent on task.

        Args:
            task: Task description

        Returns:
            Final answer/result

        Raises:
            AgentError: If execution fails
            MaxStepsExceeded: If max_steps reached without answer
        """
        ...


@runtime_checkable
class ReflectiveAgent(Protocol):
    """Agent with self-reflection capability"""

    async def run_with_reflection(
        self,
        task: str,
        reflection_trigger: str = "ERROR"
    ) -> dict[str, Any]:
        """
        Run with reflection on errors.

        Returns:
            {
                "answer": str,
                "reflections": list[str],
                "steps": int
            }
        """
        ...


# ==========================================
# Router Protocols
# ==========================================

@runtime_checkable
class Router(Protocol):
    """
    Protocol for routing/dispatching queries.

    Implementations:
    - LLMRouter (LLM-based routing)
    - RuleRouter (rule-based routing)
    - HybridRouter (combination)
    """

    async def route(self, query: str) -> str:
        """
        Route query to appropriate destination.

        Args:
            query: User query

        Returns:
            Destination identifier (e.g., "vector_db", "sql_database")
        """
        ...


@runtime_checkable
class WeightedRouter(Protocol):
    """Router that returns routing weights (for ensemble)"""

    async def route_weighted(
        self,
        query: str
    ) -> dict[str, float]:
        """
        Route with weights for each destination.

        Returns:
            {destination: weight} where sum(weights) = 1.0
        """
        ...


# ==========================================
# MoE Expert Protocols
# ==========================================

@runtime_checkable
class Expert(Protocol):
    """
    Protocol for MoE experts.

    Each expert is a feed-forward network (typically SwiGLU).
    """

    expert_id: int
    hidden_dim: int
    intermediate_dim: int

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass through expert.

        Args:
            x: Input hidden state [hidden_dim]

        Returns:
            Output hidden state [hidden_dim]
        """
        ...


@runtime_checkable
class QuantumExpert(Protocol):
    """Expert with quantum token handling"""

    def forward_quantum(
        self,
        x: np.ndarray,
        quantum_state: Any  # QuantumState from quantum_moe.py
    ) -> np.ndarray:
        """Forward pass with quantum token encoding"""
        ...


# ==========================================
# Gating Network Protocols
# ==========================================

@runtime_checkable
class GatingNetwork(Protocol):
    """
    Protocol for MoE gating/routing.

    Implementations:
    - Top-K Gating
    - Top-K with noise
    - Learned routing
    """

    num_experts: int
    top_k: int

    def gate(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute gating weights.

        Args:
            x: Input hidden state

        Returns:
            (expert_indices, expert_weights)
            - expert_indices: [top_k] indices of selected experts
            - expert_weights: [top_k] routing weights
        """
        ...


# ==========================================
# Scanner Protocols
# ==========================================

@runtime_checkable
class CodeScanner(Protocol):
    """Protocol for code analysis/scanning"""

    async def scan_file(self, file_path: str) -> dict[str, Any]:
        """
        Scan single file.

        Returns:
            {
                "classes": list[str],
                "functions": list[str],
                "imports": list[str],
                ...
            }
        """
        ...

    async def scan_directory(self, root: str) -> dict[str, Any]:
        """Scan entire directory recursively"""
        ...


@runtime_checkable
class DependencyAnalyzer(Protocol):
    """Analyze code dependencies"""

    async def build_graph(self, root: str) -> dict[str, Any]:
        """
        Build dependency graph.

        Returns:
            {
                "nodes": list[str],  # File paths
                "edges": list[tuple[str, str]],  # (source, target)
                "forward": dict,  # file -> dependencies
                "reverse": dict   # file -> dependents
            }
        """
        ...


# ==========================================
# Ledger/Evidence Protocols
# ==========================================

@runtime_checkable
class EvidenceLedger(Protocol):
    """Protocol for append-only evidence logging"""

    async def append(
        self,
        event_type: str,
        data: bytes,
        metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Append evidence record.

        Returns:
            Record metadata (timestamp, hash, signature)
        """
        ...

    async def verify_chain(self) -> bool:
        """Verify cryptographic chain integrity"""
        ...


# ==========================================
# Type Checking Helpers
# ==========================================

def is_retriever(obj: Any) -> bool:
    """Check if object implements Retriever protocol"""
    return isinstance(obj, Retriever)


def is_model(obj: Any) -> bool:
    """Check if object implements Model protocol"""
    return isinstance(obj, Model)


def is_agent(obj: Any) -> bool:
    """Check if object implements Agent protocol"""
    return isinstance(obj, Agent)

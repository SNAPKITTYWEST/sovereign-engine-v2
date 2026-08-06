"""
SOVEREIGN PYTHON LLM ENGINE
Main public API

Exports all top-level components for easy integration:
- Engine orchestration (SovereignEngine, EngineConfig, run_task, ReActAgent, ShadowAgent)
- Tool ecosystem (ToolRegistry, load_all_tools, ApprovalEngine)
- Evidence & integrity (WORMLedger, PathJail, SSRFGuard)
- Continuity layer (ContinuityManager)
- Routing & MoE (RoutingPipeline, JordanMoEGate, SpinFactor, SwarmComposer)
- Retrieval (RAGPipeline)
"""

from .sovereign import SovereignEngine, EngineConfig, run_task

from .agents import (
    ReActAgent,
    MCTSAgent,
)

from .agents.shadow import ShadowAgent

from .tools import (
    ToolRegistry,
    ToolDefinition,
    RiskClass,
    ApprovalPolicy,
    load_all_tools,
    ApprovalEngine,
)

from .core import (
    WORMLedger,
    EvidenceRecord,
    WORMFile,
    CheckpointFile,
    PathJail,
    SSRFGuard,
    hash_content,
    sign_artifact,
    generate_signing_key,
)

from .continuity import (
    ContinuityManager,
)

from .routing import (
    RoutingPipeline,
    JordanMoEGate,
    SpinFactor,
    SwarmComposer,
    SparseActivation,
    RoutingWeights,
    AgentDispatch,
    DispatchResult,
)

from .retrieval import (
    RAGPipeline,
    PipelineConfig,
    SemanticChunker,
    ChunkConfig,
    ChunkStrategy,
)

__all__ = [
    # Sovereign engine
    "SovereignEngine",
    "EngineConfig",
    "run_task",

    # Agents
    "ReActAgent",
    "MCTSAgent",
    "ShadowAgent",

    # Tools
    "ToolRegistry",
    "ToolDefinition",
    "RiskClass",
    "ApprovalPolicy",
    "load_all_tools",
    "ApprovalEngine",

    # Core (crypto, integrity, evidence)
    "WORMLedger",
    "EvidenceRecord",
    "WORMFile",
    "CheckpointFile",
    "PathJail",
    "SSRFGuard",
    "hash_content",
    "sign_artifact",
    "generate_signing_key",

    # Continuity
    "ContinuityManager",

    # Routing & MoE
    "RoutingPipeline",
    "JordanMoEGate",
    "SpinFactor",
    "SwarmComposer",
    "SparseActivation",
    "RoutingWeights",
    "AgentDispatch",
    "DispatchResult",

    # Retrieval
    "RAGPipeline",
    "PipelineConfig",
    "SemanticChunker",
    "ChunkConfig",
    "ChunkStrategy",
]

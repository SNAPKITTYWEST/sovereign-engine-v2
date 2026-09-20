# Interface Reference — Sovereign Engine v2

PUBLIC INTERFACES BY MAJOR MODULE

AGENTS.REACT:
- class ReActAgent
  - __init__(model, tool_registry, config, agent_id)
  - async run(task: Task) -> str
  - async run_stream(task: Task) -> AsyncIterator[AgentStep]
  - async _execute_action(action_text: str) -> str
  - async _reflect(messages: List[Message]) -> str
  - get_trajectory() -> AgentTrajectory

- class ReActConfig
  - max_steps: int = 10
  - reflection_on_error: bool = True
  - log_to_worm: bool = True

ROUTING.PIPELINE:
- class RoutingPipeline
  - __init__(experts, top_k, routing_nodes, nand_conflicts)
  - async route(input_text: str, context: dict) -> DispatchResult
  - async route_with_trace(input_text, context) -> PipelineTrace
  - add_constraint(constraint: Constraint) -> None
  - add_nand_conflict(expert_a, expert_b, reason) -> None

ROUTING.JORDAN_MOE:
- class JordanMoE
  - __init__(dimension: int, n_experts: int)
  - route(task_embedding: Tensor) -> MoEGatingOutput
  - add_expert(name: str, expert: JordanExpert) -> None

- class SpinFactor
  - scalar: float
  - vector: List[float]
  - jordan_product(other: SpinFactor) -> SpinFactor
  - normalize() -> SpinFactor
  - eigenvalue_bounds() -> Tuple[float, float]

TOOLS.REGISTRY:
- class ToolRegistry
  - register(tool: ToolDefinition) -> None
  - unregister(tool_id: str) -> None
  - get(tool_id: str) -> ToolDefinition | None
  - list_all() -> List[ToolDefinition]
  - get_by_risk_class(risk: RiskClass) -> List[ToolDefinition]
  - get_by_tag(tag: str) -> List[ToolDefinition]

- class ToolDefinition
  - tool_id: str
  - version: str
  - title: str
  - description: str
  - input_schema: dict
  - output_schema: dict | None
  - risk_class: RiskClass
  - approval_policy: ApprovalPolicy
  - validate_input(params: dict) -> Tuple[bool, str | None]
  - validate_output(result: dict) -> Tuple[bool, str | None]

INFERENCE.BEDROCK:
- class BedrockBackend
  - __init__(model_id: str, region: str)
  - async generate(messages: List[Message], temperature: float) -> str
  - async stream(messages: List[Message]) -> AsyncIterator[str]

MODELS.ENTITIES:
- class Message
  - role: MessageRole
  - content: str
  - metadata: dict
  - timestamp: datetime

- class Conversation
  - messages: List[Message]
  - add_message(role: MessageRole, content: str) -> None
  - get_last_message() -> Message | None
  - get_messages_by_role(role: MessageRole) -> List[Message]
  - to_dict_list() -> List[dict]

- class Task
  - id: TaskID
  - description: str
  - status: TaskStatus
  - result: str | None
  - error: str | None
  - mark_in_progress(agent_id: AgentID) -> None
  - mark_completed(result: str) -> None
  - mark_failed(error: str) -> None

- class AgentTrajectory
  - task_id: TaskID
  - agent_id: AgentID
  - steps: List[AgentStep]
  - final_answer: str | None
  - add_step(...) -> AgentStep
  - get_step_count() -> int

RUNTIME.SOVEREIGN_MACHINE:
- class SovereignVM
  - async execute(bytecode: bytes) -> ExecutionResult
  - set_resource_limits(stack_depth: int, memory_mb: int) -> None
  - get_state() -> VMState

- class MachineConfig
  - entropy_threshold: float = 0.20
  - enable_native: bool = False
  - trust_registry: Set[str]
  - worm_seal: bool = True

CONTINUITY.MANAGER:
- class ContinuityManager
  - transition(from_state: str, to_state: str) -> None
  - set_states(states: Set[str]) -> None
  - set_step(step: int) -> None
  - get_step() -> int
  - snapshot() -> ContinuitySnapshot
  - was_restarted() -> bool

CORE.TYPES:
- class PositiveInt(BaseModel)
  - value: int (> 0)

- class Temperature(BaseModel)
  - value: float (in [0.0, 2.0])
  - deterministic() -> Temperature
  - standard() -> Temperature

- class JordanEigenvalue(BaseModel)
  - value: float (in [-1.0, 1.0])

CORE.CRYPTO:
- hash_content(data: bytes) -> ContentHash
- sign_data(data: bytes, key: str) -> Signature
- verify_signature(data: bytes, sig: Signature, key: str) -> bool
- blake3_digest(data: bytes) -> str
- ed25519_keypair() -> Tuple[str, str]

CORE.STORAGE:
- class StorageBackend
  - get(key: str) -> bytes
  - put(key: str, value: bytes) -> None
  - append(key: str, data: bytes) -> None  (WORM-only)
  - list_entries() -> List[str]
  - delete(key: str) -> None

RESONANCE.FABRIC:
- class SemanticFabric
  - weave(embeddings: List[Tensor]) -> Tensor
  - add_context(context: Tensor) -> None

ENTROPY.WORM:
- class WORMLedger
  - append(data: bytes) -> int  (returns offset)
  - read(offset: int, length: int) -> bytes
  - seal(entry_id: int, signature: Signature) -> bool

RUNTIME.SANDBOX:
- class CodeSandbox
  - __init__(timeout: float = 10.0, max_output_length: int = 4000)
  - async execute_python(code: str) -> CodeExecutionResult
  - async execute_bash(script: str) -> CodeExecutionResult

ENUMS:

RiskClass (int):
  0 PURE_COMPUTATION
  1 READ_ONLY_LOCAL
  2 READ_ONLY_REMOTE
  3 REVERSIBLE_LOCAL_WRITE
  4 REVERSIBLE_REMOTE_WRITE
  5 DESTRUCTIVE_LOCAL
  6 DESTRUCTIVE_REMOTE
  7 PRIVILEGED_INFRASTRUCTURE
  8 FINANCIAL_OR_LEGAL

ApprovalPolicy (int):
  0 AUTOMATIC
  1 USER_CONFIRMATION
  2 ADMIN_ONLY
  3 NEVER

MessageRole (str):
  SYSTEM, USER, ASSISTANT, TOOL, IPYTHON

TaskStatus (str):
  PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED

ActionType (str):
  THOUGHT, EXECUTE_CODE, EXECUTE_TOOL, REFLECT, FINAL_ANSWER



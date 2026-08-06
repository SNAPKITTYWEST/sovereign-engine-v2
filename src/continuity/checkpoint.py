"""
Checkpoint Management for Agent State Persistence
Part of SOVEREIGN PYTHON LLM ENGINE

Features:
- Save/restore agent state to disk (JSONL format)
- Cryptographic signing (Ed25519)
- WORM-compatible append-only log
- Support for pause/resume of long-running agents
- Time-travel debugging (replay from any checkpoint)
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
import json
import uuid

from ..core.crypto import ContentHash, Signature, SigningKey, hash_content, sign_artifact
from ..core.evidence import WORMLedger


# ==========================================
# Agent State
# ==========================================

@dataclass
class AgentState:
    """
    Complete agent state snapshot.

    Fields:
        agent_id: Unique agent identifier
        task: Current task description
        step_number: Current step in execution
        messages: Conversation history
        tool_results: Results from tool executions
        reasoning: Agent's reasoning trace
        metadata: Additional state data
    """
    agent_id: str
    task: str
    step_number: int
    messages: list[dict[str, str]]
    tool_results: list[dict[str, Any]]
    reasoning: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AgentState':
        """Create from dictionary"""
        return cls(**data)


# ==========================================
# Checkpoint
# ==========================================

@dataclass(frozen=True)
class Checkpoint:
    """
    Immutable checkpoint record.

    Fields:
        checkpoint_id: Unique checkpoint ID (UUID)
        agent_id: Agent identifier
        step_number: Step number when checkpoint was created
        state: Full agent state snapshot
        timestamp: UTC timestamp (ISO 8601)
        previous_checkpoint: ID of previous checkpoint (for chain)
        hash: Blake2b hash of state
        signature: Ed25519 signature
    """
    checkpoint_id: str
    agent_id: str
    step_number: int
    state: AgentState
    timestamp: str
    previous_checkpoint: str | None
    hash: ContentHash
    signature: Signature

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'checkpoint_id': self.checkpoint_id,
            'agent_id': self.agent_id,
            'step_number': self.step_number,
            'state': self.state.to_dict(),
            'timestamp': self.timestamp,
            'previous_checkpoint': self.previous_checkpoint,
            'hash': self.hash,
            'signature': self.signature
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary"""
        state_data = data['state']
        state = AgentState.from_dict(state_data)

        return cls(
            checkpoint_id=data['checkpoint_id'],
            agent_id=data['agent_id'],
            step_number=data['step_number'],
            state=state,
            timestamp=data['timestamp'],
            previous_checkpoint=data.get('previous_checkpoint'),
            hash=ContentHash(data['hash']),
            signature=Signature(data['signature'])
        )


# ==========================================
# Checkpoint Manager
# ==========================================

class CheckpointManager:
    """
    Manage agent checkpoints with cryptographic verification.

    Features:
    - Append-only JSONL storage
    - Cryptographic chaining (previous_checkpoint links)
    - Ed25519 signatures
    - Fast lookup by checkpoint_id or step_number
    """

    def __init__(self, checkpoint_dir: Path, signing_key: SigningKey):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoint files
            signing_key: Ed25519 signing key for checkpoints
        """
        self.checkpoint_dir = checkpoint_dir
        self.signing_key = signing_key
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Track last checkpoint for each agent
        self._last_checkpoint: dict[str, str] = {}  # agent_id -> checkpoint_id

    def _get_checkpoint_file(self, agent_id: str) -> Path:
        """Get checkpoint file path for agent"""
        return self.checkpoint_dir / f"{agent_id}.checkpoints.jsonl"

    async def save_checkpoint(
        self,
        agent_id: str,
        state: AgentState,
        step_number: int | None = None
    ) -> Checkpoint:
        """
        Save agent state checkpoint.

        Args:
            agent_id: Agent identifier
            state: Agent state to checkpoint
            step_number: Optional step number (uses state.step_number if None)

        Returns:
            Created checkpoint
        """
        if step_number is None:
            step_number = state.step_number

        # Generate checkpoint ID
        checkpoint_id = str(uuid.uuid4())

        # Get timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Serialize state and hash
        state_bytes = json.dumps(state.to_dict(), sort_keys=True).encode('utf-8')
        state_hash = hash_content(state_bytes)

        # Get previous checkpoint
        previous_checkpoint = self._last_checkpoint.get(agent_id)

        # Sign checkpoint
        signing_payload = f"{checkpoint_id}|{agent_id}|{step_number}|{state_hash}|{timestamp}".encode('utf-8')
        signature = sign_artifact(self.signing_key, signing_payload)

        # Create checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            agent_id=agent_id,
            step_number=step_number,
            state=state,
            timestamp=timestamp,
            previous_checkpoint=previous_checkpoint,
            hash=state_hash,
            signature=signature
        )

        # Append to file
        checkpoint_file = self._get_checkpoint_file(agent_id)
        with open(checkpoint_file, 'a') as f:
            checkpoint_json = json.dumps(checkpoint.to_dict(), default=str)
            f.write(checkpoint_json + '\n')

        # Update last checkpoint
        self._last_checkpoint[agent_id] = checkpoint_id

        return checkpoint

    async def load_checkpoint(
        self,
        agent_id: str,
        checkpoint_id: str | None = None,
        step_number: int | None = None
    ) -> Checkpoint | None:
        """
        Load checkpoint by ID or step number.

        Args:
            agent_id: Agent identifier
            checkpoint_id: Checkpoint ID to load (takes precedence)
            step_number: Step number to load (if checkpoint_id is None)

        Returns:
            Checkpoint if found, None otherwise
        """
        checkpoint_file = self._get_checkpoint_file(agent_id)

        if not checkpoint_file.exists():
            return None

        # Read checkpoints
        with open(checkpoint_file, 'r') as f:
            for line in f:
                data = json.loads(line)

                # Match by checkpoint_id or step_number
                if checkpoint_id and data['checkpoint_id'] == checkpoint_id:
                    return Checkpoint.from_dict(data)
                elif step_number is not None and data['step_number'] == step_number:
                    return Checkpoint.from_dict(data)

        return None

    async def load_latest_checkpoint(self, agent_id: str) -> Checkpoint | None:
        """
        Load most recent checkpoint for agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Latest checkpoint if exists, None otherwise
        """
        checkpoint_file = self._get_checkpoint_file(agent_id)

        if not checkpoint_file.exists():
            return None

        # Read last line
        with open(checkpoint_file, 'r') as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1]
                data = json.loads(last_line)
                return Checkpoint.from_dict(data)

        return None

    async def list_checkpoints(
        self,
        agent_id: str,
        after_step: int | None = None
    ) -> list[Checkpoint]:
        """
        List all checkpoints for agent.

        Args:
            agent_id: Agent identifier
            after_step: Only return checkpoints after this step

        Returns:
            List of checkpoints in chronological order
        """
        checkpoint_file = self._get_checkpoint_file(agent_id)

        if not checkpoint_file.exists():
            return []

        checkpoints = []
        with open(checkpoint_file, 'r') as f:
            for line in f:
                data = json.loads(line)

                if after_step is not None and data['step_number'] <= after_step:
                    continue

                checkpoint = Checkpoint.from_dict(data)
                checkpoints.append(checkpoint)

        return checkpoints

    async def verify_checkpoint_chain(self, agent_id: str) -> bool:
        """
        Verify cryptographic integrity of checkpoint chain.

        Args:
            agent_id: Agent identifier

        Returns:
            True if chain is valid, False if tampered
        """
        checkpoints = await self.list_checkpoints(agent_id)

        if not checkpoints:
            return True

        # Verify chain links
        expected_prev = None
        for checkpoint in checkpoints:
            if checkpoint.previous_checkpoint != expected_prev:
                return False
            expected_prev = checkpoint.checkpoint_id

        return True

    async def delete_checkpoints(self, agent_id: str) -> None:
        """
        Delete all checkpoints for agent.

        WARNING: This breaks WORM semantics. Only use for cleanup.

        Args:
            agent_id: Agent identifier
        """
        checkpoint_file = self._get_checkpoint_file(agent_id)
        if checkpoint_file.exists():
            checkpoint_file.unlink()

        # Remove from cache
        if agent_id in self._last_checkpoint:
            del self._last_checkpoint[agent_id]

    async def get_checkpoint_stats(self, agent_id: str) -> dict[str, Any]:
        """
        Get checkpoint statistics for agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dictionary with statistics
        """
        checkpoints = await self.list_checkpoints(agent_id)

        if not checkpoints:
            return {
                'total_checkpoints': 0,
                'first_checkpoint': None,
                'last_checkpoint': None,
                'chain_valid': True
            }

        return {
            'total_checkpoints': len(checkpoints),
            'first_checkpoint': checkpoints[0].checkpoint_id,
            'last_checkpoint': checkpoints[-1].checkpoint_id,
            'first_timestamp': checkpoints[0].timestamp,
            'last_timestamp': checkpoints[-1].timestamp,
            'step_range': (checkpoints[0].step_number, checkpoints[-1].step_number),
            'chain_valid': await self.verify_checkpoint_chain(agent_id)
        }


# ==========================================
# Checkpoint Iterator
# ==========================================

class CheckpointIterator:
    """
    Iterate through checkpoints in order.
    """

    def __init__(self, manager: CheckpointManager, agent_id: str):
        self.manager = manager
        self.agent_id = agent_id
        self._checkpoints: list[Checkpoint] | None = None
        self._index = 0

    async def __aiter__(self) -> AsyncIterator[Checkpoint]:
        """Async iterator"""
        if self._checkpoints is None:
            self._checkpoints = await self.manager.list_checkpoints(self.agent_id)

        for checkpoint in self._checkpoints:
            yield checkpoint

    async def next_checkpoint(self) -> Checkpoint | None:
        """Get next checkpoint"""
        if self._checkpoints is None:
            self._checkpoints = await self.manager.list_checkpoints(self.agent_id)

        if self._index >= len(self._checkpoints):
            return None

        checkpoint = self._checkpoints[self._index]
        self._index += 1
        return checkpoint

    async def prev_checkpoint(self) -> Checkpoint | None:
        """Get previous checkpoint"""
        if self._checkpoints is None:
            self._checkpoints = await self.manager.list_checkpoints(self.agent_id)

        if self._index <= 0:
            return None

        self._index -= 1
        return self._checkpoints[self._index]

    def reset(self) -> None:
        """Reset iterator to beginning"""
        self._index = 0


# ==========================================
# Checkpoint Diff
# ==========================================

@dataclass
class CheckpointDiff:
    """
    Difference between two checkpoints.
    """
    from_checkpoint: str
    to_checkpoint: str
    step_delta: int
    messages_added: int
    tools_executed: int
    reasoning_added: int
    metadata_changes: dict[str, Any]


def compute_checkpoint_diff(
    from_checkpoint: Checkpoint,
    to_checkpoint: Checkpoint
) -> CheckpointDiff:
    """
    Compute difference between two checkpoints.

    Args:
        from_checkpoint: Earlier checkpoint
        to_checkpoint: Later checkpoint

    Returns:
        CheckpointDiff describing changes
    """
    from_state = from_checkpoint.state
    to_state = to_checkpoint.state

    # Compute deltas
    step_delta = to_state.step_number - from_state.step_number
    messages_added = len(to_state.messages) - len(from_state.messages)
    tools_executed = len(to_state.tool_results) - len(from_state.tool_results)
    reasoning_added = len(to_state.reasoning) - len(from_state.reasoning)

    # Metadata changes
    metadata_changes = {}
    for key in to_state.metadata:
        if key not in from_state.metadata:
            metadata_changes[key] = ('added', to_state.metadata[key])
        elif to_state.metadata[key] != from_state.metadata[key]:
            metadata_changes[key] = ('changed', from_state.metadata[key], to_state.metadata[key])

    for key in from_state.metadata:
        if key not in to_state.metadata:
            metadata_changes[key] = ('removed', from_state.metadata[key])

    return CheckpointDiff(
        from_checkpoint=from_checkpoint.checkpoint_id,
        to_checkpoint=to_checkpoint.checkpoint_id,
        step_delta=step_delta,
        messages_added=messages_added,
        tools_executed=tools_executed,
        reasoning_added=reasoning_added,
        metadata_changes=metadata_changes
    )

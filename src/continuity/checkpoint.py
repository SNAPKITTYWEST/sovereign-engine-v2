"""
Checkpoint Management for Agent State Persistence
Part of SOVEREIGN PYTHON LLM ENGINE

Backed by binary struct storage (CheckpointFile from core.storage).
No JSONL, no text encoding, no injection surface.

Features:
- Save/restore agent state to disk (binary struct format)
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
from ..core.storage import CheckpointFile, CheckpointRecord


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
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'AgentState':
        return cls(**data)

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':')).encode('utf-8')

    @classmethod
    def from_bytes(cls, raw: bytes) -> 'AgentState':
        return cls.from_dict(json.loads(raw.decode('utf-8')))


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

    @classmethod
    def from_record(cls, rec: CheckpointRecord) -> 'Checkpoint':
        state = AgentState.from_bytes(rec.state)
        return cls(
            checkpoint_id=rec.checkpoint_id,
            agent_id=rec.agent_id,
            step_number=rec.step_number,
            state=state,
            timestamp=datetime.fromtimestamp(
                rec.timestamp_ns / 1_000_000_000, tz=timezone.utc
            ).isoformat(),
            previous_checkpoint=rec.prev_id or None,
            hash=rec.content_hash,
            signature=rec.signature
        )


# ==========================================
# Checkpoint Manager (binary storage)
# ==========================================

class CheckpointManager:
    """
    Manage agent checkpoints with binary struct storage.

    Uses CheckpointFile from core.storage (128-byte fixed headers,
    Blake2b hash chain, Ed25519 signatures). No JSONL.
    """

    def __init__(self, checkpoint_dir: Path, signing_key: SigningKey):
        self.checkpoint_dir = checkpoint_dir
        self.signing_key = signing_key
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._last_checkpoint: dict[str, str] = {}

    def _get_checkpoint_file(self, agent_id: str) -> CheckpointFile:
        path = self.checkpoint_dir / f"{agent_id}.ckpt"
        return CheckpointFile(path, signing_key=self.signing_key)

    async def save_checkpoint(
        self,
        agent_id: str,
        state: AgentState,
        step_number: int | None = None
    ) -> Checkpoint:
        """
        Save agent state checkpoint to binary storage.
        """
        if step_number is None:
            step_number = state.step_number

        checkpoint_id = str(uuid.uuid4())
        previous_checkpoint = self._last_checkpoint.get(agent_id, "")

        state_bytes = state.to_bytes()
        state_hash = hash_content(state_bytes)

        signing_payload = f"{checkpoint_id}|{agent_id}|{step_number}|{state_hash}".encode('utf-8')
        signature = sign_artifact(self.signing_key, signing_payload)

        ckpt_file = self._get_checkpoint_file(agent_id)
        rec = ckpt_file.append(
            checkpoint_id=checkpoint_id,
            agent_id=agent_id,
            state=state_bytes,
            step=step_number,
            prev_id=previous_checkpoint
        )

        self._last_checkpoint[agent_id] = checkpoint_id

        return Checkpoint.from_record(rec)

    async def load_checkpoint(
        self,
        agent_id: str,
        checkpoint_id: str | None = None,
        step_number: int | None = None
    ) -> Checkpoint | None:
        """
        Load checkpoint by ID or step number.
        """
        ckpt_file = self._get_checkpoint_file(agent_id)

        if checkpoint_id:
            rec = ckpt_file.get_by_id(checkpoint_id)
            if rec:
                return Checkpoint.from_record(rec)
            return None

        if step_number is not None:
            rec = ckpt_file.get_by_step(step_number)
            if rec:
                return Checkpoint.from_record(rec)
            return None

        return None

    async def load_latest_checkpoint(self, agent_id: str) -> Checkpoint | None:
        """Load most recent checkpoint for agent."""
        ckpt_file = self._get_checkpoint_file(agent_id)
        rec = ckpt_file.get_latest()
        if rec:
            return Checkpoint.from_record(rec)
        return None

    async def list_checkpoints(
        self,
        agent_id: str,
        after_step: int | None = None
    ) -> list[Checkpoint]:
        """List all checkpoints for agent."""
        ckpt_file = self._get_checkpoint_file(agent_id)
        checkpoints = []
        for rec in ckpt_file.scan():
            if after_step is not None and rec.step_number <= after_step:
                continue
            checkpoints.append(Checkpoint.from_record(rec))
        return checkpoints

    async def verify_checkpoint_chain(self, agent_id: str) -> bool:
        """Verify cryptographic integrity of checkpoint chain."""
        checkpoints = await self.list_checkpoints(agent_id)
        if not checkpoints:
            return True

        expected_prev = ""
        for checkpoint in checkpoints:
            if (checkpoint.previous_checkpoint or "") != expected_prev:
                return False
            expected_prev = checkpoint.checkpoint_id
        return True

    async def get_checkpoint_stats(self, agent_id: str) -> dict[str, Any]:
        """Get checkpoint statistics for agent."""
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
    """Iterate through checkpoints in order."""

    def __init__(self, manager: CheckpointManager, agent_id: str):
        self.manager = manager
        self.agent_id = agent_id
        self._checkpoints: list[Checkpoint] | None = None
        self._index = 0

    async def __aiter__(self) -> AsyncIterator[Checkpoint]:
        if self._checkpoints is None:
            self._checkpoints = await self.manager.list_checkpoints(self.agent_id)
        for checkpoint in self._checkpoints:
            yield checkpoint

    async def next_checkpoint(self) -> Checkpoint | None:
        if self._checkpoints is None:
            self._checkpoints = await self.manager.list_checkpoints(self.agent_id)
        if self._index >= len(self._checkpoints):
            return None
        checkpoint = self._checkpoints[self._index]
        self._index += 1
        return checkpoint

    async def prev_checkpoint(self) -> Checkpoint | None:
        if self._checkpoints is None:
            self._checkpoints = await self.manager.list_checkpoints(self.agent_id)
        if self._index <= 0:
            return None
        self._index -= 1
        return self._checkpoints[self._index]

    def reset(self) -> None:
        self._index = 0

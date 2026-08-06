"""
Layer 11: Continuity — Four-Paradigm Agent State Persistence
Part of SOVEREIGN PYTHON LLM ENGINE

Paradigm 1: EnvStateMachine   — OS environment bitmask + exec restart
Paradigm 2: SeedChain         — Functional seed continuity (compress history to 8 bytes)
Paradigm 3: InodeStateMachine — Zero-byte filesystem flags (kernel dcache speed)
Paradigm 4: SharedStateBlock  — ctypes shared memory (RAM speed, zero serialization)

Unified: ContinuityManager — all four backends behind one interface
Classic: CheckpointManager + ReplayEngine — binary struct checkpoints + time-travel
"""

from .checkpoint   import Checkpoint, CheckpointManager, AgentState
from .replay       import ReplayEngine, ReplaySession, ReplayEvent
from .env_state    import EnvStateMachine, DaemonRestarter, PipeStateTransfer
from .seed_state   import SeedChain, SeedLedger, OpLog
from .inode_state  import InodeStateMachine, InodeRegistry, InodeGate
from .shared_mem   import SharedStateBlock, SharedMemoryState
from .manager      import ContinuityManager, ContinuitySnapshot

__all__ = [
    # Classic
    'Checkpoint', 'CheckpointManager', 'AgentState',
    'ReplayEngine', 'ReplaySession', 'ReplayEvent',
    # Paradigm 1
    'EnvStateMachine', 'DaemonRestarter', 'PipeStateTransfer',
    # Paradigm 2
    'SeedChain', 'SeedLedger', 'OpLog',
    # Paradigm 3
    'InodeStateMachine', 'InodeRegistry', 'InodeGate',
    # Paradigm 4
    'SharedStateBlock', 'SharedMemoryState',
    # Unified
    'ContinuityManager', 'ContinuitySnapshot',
]

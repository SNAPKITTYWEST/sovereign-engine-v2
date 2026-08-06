"""
Replay Engine for Time-Travel Debugging
Part of SOVEREIGN PYTHON LLM ENGINE

Features:
- Replay agent execution from checkpoint
- Deterministic replay (same inputs → same outputs)
- Fast-forward to specific step
- Inject new state at any point (branching timelines)
- Event log reconstruction
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable
import json

from .checkpoint import Checkpoint, CheckpointManager, AgentState


# ==========================================
# Replay Event
# ==========================================

@dataclass
class ReplayEvent:
    """
    Single event in replay timeline.

    Fields:
        event_id: Unique event ID
        event_type: Type of event (e.g., 'tool_call', 'reasoning', 'message')
        step_number: Step when event occurred
        timestamp: Event timestamp
        data: Event data
    """
    event_id: str
    event_type: str
    step_number: int
    timestamp: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ReplayEvent':
        """Create from dictionary"""
        return cls(**data)


# ==========================================
# Replay Session
# ==========================================

@dataclass
class ReplaySession:
    """
    Replay session metadata.

    Fields:
        session_id: Unique session ID
        agent_id: Agent being replayed
        start_checkpoint: Starting checkpoint ID
        end_checkpoint: Ending checkpoint ID (None if ongoing)
        events: List of replay events
        branches: Timeline branches (for "what if" scenarios)
    """
    session_id: str
    agent_id: str
    start_checkpoint: str
    end_checkpoint: str | None
    events: list[ReplayEvent]
    branches: dict[str, str]  # branch_name -> checkpoint_id

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'start_checkpoint': self.start_checkpoint,
            'end_checkpoint': self.end_checkpoint,
            'events': [e.to_dict() for e in self.events],
            'branches': self.branches
        }


# ==========================================
# Replay Engine
# ==========================================

class ReplayEngine:
    """
    Engine for replaying agent execution from checkpoints.

    Features:
    - Deterministic replay
    - Fast-forward to specific checkpoint
    - Event-by-event stepping
    - Timeline branching
    """

    def __init__(self, checkpoint_manager: CheckpointManager):
        """
        Initialize replay engine.

        Args:
            checkpoint_manager: Checkpoint manager for loading state
        """
        self.checkpoint_manager = checkpoint_manager
        self.sessions: dict[str, ReplaySession] = {}

    async def start_replay(
        self,
        agent_id: str,
        from_checkpoint: str | None = None,
        to_checkpoint: str | None = None
    ) -> ReplaySession:
        """
        Start replay session.

        Args:
            agent_id: Agent to replay
            from_checkpoint: Starting checkpoint (None = first checkpoint)
            to_checkpoint: Ending checkpoint (None = latest checkpoint)

        Returns:
            ReplaySession
        """
        import uuid

        # Get checkpoints
        checkpoints = await self.checkpoint_manager.list_checkpoints(agent_id)

        if not checkpoints:
            raise ValueError(f"No checkpoints found for agent {agent_id}")

        # Determine start/end
        if from_checkpoint is None:
            start_checkpoint = checkpoints[0].checkpoint_id
        else:
            start_checkpoint = from_checkpoint

        if to_checkpoint is None:
            end_checkpoint = checkpoints[-1].checkpoint_id
        else:
            end_checkpoint = to_checkpoint

        # Create session
        session_id = str(uuid.uuid4())
        session = ReplaySession(
            session_id=session_id,
            agent_id=agent_id,
            start_checkpoint=start_checkpoint,
            end_checkpoint=end_checkpoint,
            events=[],
            branches={}
        )

        self.sessions[session_id] = session
        return session

    async def replay_to_checkpoint(
        self,
        session_id: str,
        target_checkpoint: str
    ) -> AgentState:
        """
        Fast-forward replay to target checkpoint.

        Args:
            session_id: Replay session ID
            target_checkpoint: Checkpoint to replay to

        Returns:
            Agent state at target checkpoint
        """
        session = self.sessions[session_id]

        # Load target checkpoint
        checkpoint = await self.checkpoint_manager.load_checkpoint(
            session.agent_id,
            checkpoint_id=target_checkpoint
        )

        if checkpoint is None:
            raise ValueError(f"Checkpoint not found: {target_checkpoint}")

        # Reconstruct events from checkpoint history
        events = await self._reconstruct_events(
            session.agent_id,
            session.start_checkpoint,
            target_checkpoint
        )

        session.events = events
        return checkpoint.state

    async def replay_to_step(
        self,
        session_id: str,
        target_step: int
    ) -> AgentState:
        """
        Replay to specific step number.

        Args:
            session_id: Replay session ID
            target_step: Step number to replay to

        Returns:
            Agent state at target step
        """
        session = self.sessions[session_id]

        # Find checkpoint at or before target step
        checkpoints = await self.checkpoint_manager.list_checkpoints(session.agent_id)
        target_checkpoint = None

        for checkpoint in reversed(checkpoints):
            if checkpoint.step_number <= target_step:
                target_checkpoint = checkpoint
                break

        if target_checkpoint is None:
            raise ValueError(f"No checkpoint found at or before step {target_step}")

        return await self.replay_to_checkpoint(session_id, target_checkpoint.checkpoint_id)

    async def step_forward(self, session_id: str) -> ReplayEvent | None:
        """
        Step forward one event in replay.

        Args:
            session_id: Replay session ID

        Returns:
            Next event, or None if at end
        """
        session = self.sessions[session_id]

        # Get all events
        all_events = await self._reconstruct_events(
            session.agent_id,
            session.start_checkpoint,
            session.end_checkpoint
        )

        # Find next event
        current_event_count = len(session.events)
        if current_event_count >= len(all_events):
            return None

        next_event = all_events[current_event_count]
        session.events.append(next_event)

        return next_event

    async def step_backward(self, session_id: str) -> ReplayEvent | None:
        """
        Step backward one event in replay.

        Args:
            session_id: Replay session ID

        Returns:
            Previous event, or None if at beginning
        """
        session = self.sessions[session_id]

        if not session.events:
            return None

        return session.events.pop()

    async def create_branch(
        self,
        session_id: str,
        branch_name: str,
        from_checkpoint: str
    ) -> None:
        """
        Create timeline branch for "what if" scenarios.

        Args:
            session_id: Replay session ID
            branch_name: Name for this branch
            from_checkpoint: Checkpoint to branch from
        """
        session = self.sessions[session_id]
        session.branches[branch_name] = from_checkpoint

    async def switch_to_branch(
        self,
        session_id: str,
        branch_name: str
    ) -> AgentState:
        """
        Switch replay to a different branch.

        Args:
            session_id: Replay session ID
            branch_name: Branch to switch to

        Returns:
            Agent state at branch point
        """
        session = self.sessions[session_id]

        if branch_name not in session.branches:
            raise ValueError(f"Branch not found: {branch_name}")

        branch_checkpoint = session.branches[branch_name]
        return await self.replay_to_checkpoint(session_id, branch_checkpoint)

    async def inject_state(
        self,
        session_id: str,
        modified_state: AgentState,
        checkpoint_name: str = "injected"
    ) -> Checkpoint:
        """
        Inject modified state into replay (creates new timeline).

        Args:
            session_id: Replay session ID
            modified_state: Modified agent state
            checkpoint_name: Name for the branch

        Returns:
            New checkpoint with injected state
        """
        session = self.sessions[session_id]

        # Save as new checkpoint
        checkpoint = await self.checkpoint_manager.save_checkpoint(
            session.agent_id,
            modified_state,
            modified_state.step_number
        )

        # Create branch
        await self.create_branch(session_id, checkpoint_name, checkpoint.checkpoint_id)

        return checkpoint

    async def get_timeline_summary(self, session_id: str) -> dict[str, Any]:
        """
        Get summary of replay timeline.

        Args:
            session_id: Replay session ID

        Returns:
            Dictionary with timeline statistics
        """
        session = self.sessions[session_id]

        # Load checkpoints
        start_checkpoint = await self.checkpoint_manager.load_checkpoint(
            session.agent_id,
            checkpoint_id=session.start_checkpoint
        )
        end_checkpoint = await self.checkpoint_manager.load_checkpoint(
            session.agent_id,
            checkpoint_id=session.end_checkpoint
        ) if session.end_checkpoint else None

        # Event counts by type
        event_counts: dict[str, int] = {}
        for event in session.events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

        return {
            'session_id': session.session_id,
            'agent_id': session.agent_id,
            'start_step': start_checkpoint.step_number if start_checkpoint else None,
            'end_step': end_checkpoint.step_number if end_checkpoint else None,
            'total_events': len(session.events),
            'event_counts': event_counts,
            'branches': list(session.branches.keys())
        }

    async def _reconstruct_events(
        self,
        agent_id: str,
        from_checkpoint: str | None,
        to_checkpoint: str | None
    ) -> list[ReplayEvent]:
        """
        Reconstruct event timeline from checkpoints.

        Args:
            agent_id: Agent identifier
            from_checkpoint: Starting checkpoint
            to_checkpoint: Ending checkpoint

        Returns:
            List of events in chronological order
        """
        import uuid

        events: list[ReplayEvent] = []

        # Get checkpoint range
        checkpoints = await self.checkpoint_manager.list_checkpoints(agent_id)

        # Filter to range
        in_range = False
        for checkpoint in checkpoints:
            if from_checkpoint and checkpoint.checkpoint_id == from_checkpoint:
                in_range = True

            if not in_range:
                continue

            # Extract events from checkpoint state
            state = checkpoint.state

            # Message events
            for msg in state.messages:
                event = ReplayEvent(
                    event_id=str(uuid.uuid4()),
                    event_type='message',
                    step_number=checkpoint.step_number,
                    timestamp=checkpoint.timestamp,
                    data=msg
                )
                events.append(event)

            # Tool events
            for tool_result in state.tool_results:
                event = ReplayEvent(
                    event_id=str(uuid.uuid4()),
                    event_type='tool_call',
                    step_number=checkpoint.step_number,
                    timestamp=checkpoint.timestamp,
                    data=tool_result
                )
                events.append(event)

            # Reasoning events
            for reasoning in state.reasoning:
                event = ReplayEvent(
                    event_id=str(uuid.uuid4()),
                    event_type='reasoning',
                    step_number=checkpoint.step_number,
                    timestamp=checkpoint.timestamp,
                    data={'content': reasoning}
                )
                events.append(event)

            if to_checkpoint and checkpoint.checkpoint_id == to_checkpoint:
                break

        return events

    async def export_replay(
        self,
        session_id: str,
        output_path: Path
    ) -> None:
        """
        Export replay session to file.

        Args:
            session_id: Replay session ID
            output_path: Path to export file
        """
        session = self.sessions[session_id]

        with open(output_path, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)

    async def import_replay(
        self,
        input_path: Path
    ) -> str:
        """
        Import replay session from file.

        Args:
            input_path: Path to replay file

        Returns:
            Session ID of imported session
        """
        with open(input_path, 'r') as f:
            data = json.load(f)

        events = [ReplayEvent.from_dict(e) for e in data['events']]

        session = ReplaySession(
            session_id=data['session_id'],
            agent_id=data['agent_id'],
            start_checkpoint=data['start_checkpoint'],
            end_checkpoint=data.get('end_checkpoint'),
            events=events,
            branches=data.get('branches', {})
        )

        self.sessions[session.session_id] = session
        return session.session_id


# ==========================================
# Replay Visualization
# ==========================================

class ReplayVisualizer:
    """
    Generate visualizations of replay timelines.
    """

    def __init__(self, engine: ReplayEngine):
        self.engine = engine

    async def generate_timeline_text(self, session_id: str) -> str:
        """
        Generate text-based timeline visualization.

        Args:
            session_id: Replay session ID

        Returns:
            Text visualization of timeline
        """
        session = self.engine.sessions[session_id]
        summary = await self.engine.get_timeline_summary(session_id)

        lines = []
        lines.append(f"=== Replay Timeline: {session.session_id} ===")
        lines.append(f"Agent: {session.agent_id}")
        lines.append(f"Steps: {summary['start_step']} → {summary['end_step']}")
        lines.append(f"Total Events: {summary['total_events']}")
        lines.append("")

        lines.append("Event Distribution:")
        for event_type, count in summary['event_counts'].items():
            lines.append(f"  {event_type}: {count}")

        if session.branches:
            lines.append("")
            lines.append("Branches:")
            for branch_name in session.branches:
                lines.append(f"  - {branch_name}")

        lines.append("")
        lines.append("Event Log:")
        for event in session.events[:50]:  # First 50 events
            lines.append(f"  [{event.step_number}] {event.event_type}: {event.event_id[:8]}")

        if len(session.events) > 50:
            lines.append(f"  ... ({len(session.events) - 50} more events)")

        return "\n".join(lines)

    async def generate_event_graph(
        self,
        session_id: str
    ) -> dict[str, Any]:
        """
        Generate event graph data (for visualization tools).

        Args:
            session_id: Replay session ID

        Returns:
            Graph data structure
        """
        session = self.engine.sessions[session_id]

        # Build nodes and edges
        nodes = []
        edges = []

        prev_event_id = None
        for event in session.events:
            nodes.append({
                'id': event.event_id,
                'type': event.event_type,
                'step': event.step_number,
                'timestamp': event.timestamp
            })

            if prev_event_id:
                edges.append({
                    'from': prev_event_id,
                    'to': event.event_id
                })

            prev_event_id = event.event_id

        return {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'session_id': session.session_id,
                'agent_id': session.agent_id
            }
        }

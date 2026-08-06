"""
Approval Policy Engine
Part of SOVEREIGN PYTHON LLM ENGINE

Risk-based approval enforcement with WORM audit logging.
"""

from typing import Any, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone

from .registry import ToolDefinition, RiskClass, ApprovalPolicy
from ..core.evidence import WORMLedger


# ==========================================
# Approval Result
# ==========================================

@dataclass
class ApprovalResult:
    """
    Result of approval check.

    Fields:
        approved: Whether tool execution is approved
        reason: Reason for approval/denial
        approved_by: Who approved (None if automatic)
        timestamp: When approval was granted
    """
    approved: bool
    reason: str | None
    approved_by: str | None
    timestamp: str


# ==========================================
# Approval Engine
# ==========================================

class ApprovalEngine:
    """
    Enforce tool approval policies.

    Features:
    - Risk-based automatic approval
    - User confirmation for risky operations
    - Admin-only enforcement
    - WORM audit logging
    """

    def __init__(
        self,
        ledger: WORMLedger,
        confirmation_callback: Callable[[ToolDefinition, dict[str, Any]], Awaitable[bool]] | None = None
    ):
        """
        Initialize approval engine.

        Args:
            ledger: WORM ledger for audit logging
            confirmation_callback: Async function to request user confirmation
        """
        self.ledger = ledger
        self.confirmation_callback = confirmation_callback

    async def check_approval(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        actor: str
    ) -> ApprovalResult:
        """
        Check if tool execution requires approval.

        Args:
            tool: Tool definition
            arguments: Tool parameters
            actor: Who is executing the tool

        Returns:
            ApprovalResult
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Check approval policy
        if tool.approval_policy == ApprovalPolicy.AUTOMATIC:
            # Auto-approve
            result = ApprovalResult(
                approved=True,
                reason="Automatic approval (low risk)",
                approved_by=None,
                timestamp=timestamp
            )

        elif tool.approval_policy == ApprovalPolicy.USER_CONFIRMATION:
            # Request user confirmation
            if self.confirmation_callback:
                confirmed = await self.confirmation_callback(tool, arguments)
                result = ApprovalResult(
                    approved=confirmed,
                    reason="User confirmation" if confirmed else "User declined",
                    approved_by=actor if confirmed else None,
                    timestamp=timestamp
                )
            else:
                # No callback, deny
                result = ApprovalResult(
                    approved=False,
                    reason="User confirmation required but no callback configured",
                    approved_by=None,
                    timestamp=timestamp
                )

        elif tool.approval_policy == ApprovalPolicy.ADMIN_ONLY:
            # Check if actor is admin
            is_admin = await self._check_admin(actor)
            result = ApprovalResult(
                approved=is_admin,
                reason="Admin approval" if is_admin else "Admin privileges required",
                approved_by=actor if is_admin else None,
                timestamp=timestamp
            )

        elif tool.approval_policy == ApprovalPolicy.NEVER:
            # Tool is disabled
            result = ApprovalResult(
                approved=False,
                reason="Tool is disabled",
                approved_by=None,
                timestamp=timestamp
            )

        else:
            # Unknown policy, deny
            result = ApprovalResult(
                approved=False,
                reason=f"Unknown approval policy: {tool.approval_policy}",
                approved_by=None,
                timestamp=timestamp
            )

        # Log to WORM ledger
        await self._log_approval(tool, arguments, actor, result)

        return result

    async def check_risk_class(
        self,
        tool: ToolDefinition,
        max_allowed_risk: RiskClass
    ) -> tuple[bool, str | None]:
        """
        Check if tool risk class is within allowed threshold.

        Args:
            tool: Tool definition
            max_allowed_risk: Maximum allowed risk class

        Returns:
            (approved, reason) tuple
        """
        if tool.risk_class <= max_allowed_risk:
            return True, None
        else:
            return False, f"Tool risk class {tool.risk_class.name} exceeds maximum {max_allowed_risk.name}"

    async def _check_admin(self, actor: str) -> bool:
        """
        Check if actor has admin privileges.

        Args:
            actor: Actor identifier

        Returns:
            True if admin
        """
        # TODO: Implement admin check (e.g., check against admin list)
        # For now, return False (require explicit admin configuration)
        return False

    async def _log_approval(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        actor: str,
        result: ApprovalResult
    ) -> None:
        """
        Log approval decision to WORM ledger.

        Args:
            tool: Tool definition
            arguments: Tool parameters
            actor: Actor identifier
            result: Approval result
        """
        import json

        log_data = {
            'tool_id': tool.tool_id,
            'actor': actor,
            'approved': result.approved,
            'reason': result.reason,
            'approved_by': result.approved_by,
            'timestamp': result.timestamp,
            'risk_class': tool.risk_class.name,
            'approval_policy': tool.approval_policy.name
        }

        log_bytes = json.dumps(log_data).encode('utf-8')

        self.ledger.append(
            event_type='tool_approval',
            data=log_bytes,
            metadata=log_data
        )


# ==========================================
# Approval Statistics
# ==========================================

class ApprovalStatistics:
    """
    Track approval statistics.
    """

    def __init__(self, ledger: WORMLedger):
        self.ledger = ledger

    def get_stats(self) -> dict[str, Any]:
        """
        Get approval statistics from ledger.

        Returns:
            Dictionary with statistics
        """
        approval_records = self.ledger.get_records_by_type('tool_approval')

        total = len(approval_records)
        approved = sum(1 for r in approval_records if r.metadata.get('approved'))
        denied = total - approved

        # By risk class
        risk_distribution: dict[str, int] = {}
        for record in approval_records:
            risk_class = record.metadata.get('risk_class', 'UNKNOWN')
            risk_distribution[risk_class] = risk_distribution.get(risk_class, 0) + 1

        # By actor
        actor_distribution: dict[str, int] = {}
        for record in approval_records:
            actor = record.metadata.get('actor', 'UNKNOWN')
            actor_distribution[actor] = actor_distribution.get(actor, 0) + 1

        return {
            'total_requests': total,
            'approved': approved,
            'denied': denied,
            'approval_rate': approved / total if total > 0 else 0.0,
            'risk_distribution': risk_distribution,
            'actor_distribution': actor_distribution
        }


# ==========================================
# Terminal Confirmation UI
# ==========================================

async def terminal_confirmation(
    tool: ToolDefinition,
    arguments: dict[str, Any]
) -> bool:
    """
    Request approval via terminal prompt.

    Args:
        tool: Tool definition
        arguments: Tool parameters

    Returns:
        True if approved
    """
    import asyncio

    print("\n" + "=" * 60)
    print("TOOL APPROVAL REQUEST")
    print("=" * 60)
    print(f"Tool: {tool.tool_id}")
    print(f"Description: {tool.description}")
    print(f"Risk Class: {tool.risk_class.name}")
    print(f"\nParameters:")
    for key, value in arguments.items():
        print(f"  {key}: {value}")
    print("=" * 60)

    # Get user input
    response = await asyncio.to_thread(
        input,
        "Approve this operation? [y/N]: "
    )

    return response.lower() in ['y', 'yes']

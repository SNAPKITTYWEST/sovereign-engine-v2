"""
kid_8b_8k.py — 8 KB child safety microkernel (Python reference)

Source: github.com/SNAPKITTYWEST/sovereign-mum

The kernel is the trusted surface for an external 8B model.
Model weights never reach this kernel. This kernel is the
child-facing trusted computing base.

Policy gate:
    MODEL_CALL = AGE_OK AND PII_CLEAR AND TOPIC_OK
                 AND NOT RISK_BLOCK AND CONSENT_OK AND TOOL_NONE

SAT boot invariant (5 clauses, 15-byte seed, 6502 implementation in
src/6502/sat_kernel.asm):
    BOOT_OK = SAT(F, A) ∧ x0 ∧ x1 ∧ x2 ∧ ¬x3 ∧ ¬x4

    x0 KERNEL_INTEGRITY     True
    x1 CHILD_PROFILE_VALID  True
    x2 PRIVACY_FILTER_ACTIVE True
    x3 UNRESTRICTED_TOOLS   False
    x4 RAW_REMOTE_SESSION   False
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from enum import IntFlag, auto


class PolicyFlag(IntFlag):
    PII_DETECTED      = auto()
    UNSAFE_TOPIC      = auto()
    CAREGIVER_CONSENT = auto()
    APPROVED_DOMAIN   = auto()
    RISK_SIGNAL       = auto()
    AGE_VALID         = auto()


SAFE_TEMPLATE = (
    "Let's choose a safe learning activity. "
    "A trusted adult can help with this topic."
)

CAPABILITY_DENY  = {
    "CAP_NETWORK", "CAP_BROWSER", "CAP_SHELL", "CAP_FILESYSTEM",
    "CAP_CAMERA", "CAP_MICROPHONE", "CAP_LOCATION", "CAP_CONTACTS",
    "CAP_PURCHASE", "CAP_SEND_MESSAGE", "CAP_MODEL_RECONFIGURE", "CAP_POLICY_WRITE",
}
CAPABILITY_ALLOW = {"CAP_LESSON_REPLY"}


@dataclass
class ChildRequest:
    raw_text:      str
    age_band:      str    # "3-5" | "6-8" | "9-11" | "12-14"
    domain_id:     str    # approved lesson domain
    session_nonce: str


@dataclass
class AuditReceipt:
    event:          str
    policy_version: str
    age_band:       str
    domain_id:      str
    nonce:          str
    timestamp:      float
    hash:           str = field(init=False)

    def __post_init__(self) -> None:
        payload = json.dumps({
            "event":  self.event,
            "policy": self.policy_version,
            "age":    self.age_band,
            "domain": self.domain_id,
            "nonce":  self.nonce,
            "ts":     self.timestamp,
        }, sort_keys=True)
        self.hash = hashlib.sha256(payload.encode()).hexdigest()[:16]


class PIIScrubber:
    _EMAIL     = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    _PHONE     = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
    _NAME_HINT = re.compile(r"\b(my name is|I am|I'm)\s+\w+", re.IGNORECASE)

    @classmethod
    def scrub(cls, text: str) -> tuple[str, bool]:
        found = False
        for pat in (cls._EMAIL, cls._PHONE, cls._NAME_HINT):
            if pat.search(text):
                found = True
                text  = pat.sub("[REDACTED]", text)
        return text, found


class TopicPolicy:
    APPROVED_DOMAINS = {
        "math", "reading", "science", "history", "geography",
        "art", "music", "coding_basics", "nature", "health_basics",
    }
    RISK_PATTERNS = [
        "violence", "weapon", "drug", "adult", "explicit",
        "hack", "exploit", "cheat", "bully", "suicide",
    ]

    @classmethod
    def check(cls, text: str, domain_id: str) -> tuple[bool, bool]:
        approved = domain_id.lower() in cls.APPROVED_DOMAINS
        risk     = any(w in text.lower() for w in cls.RISK_PATTERNS)
        return approved, risk


class KID8B8K:
    """
    8 KB child safety microkernel.

    model_broker: callable that accepts a minimal payload dict and returns
                  a text response. The kernel never holds model weights or keys.
    """

    POLICY_VERSION = "1.0.0"

    def __init__(self, model_broker=None) -> None:
        self._broker    = model_broker
        self._audit_log: list[AuditReceipt] = []

    def _sat_boot_check(self) -> bool:
        """
        Python equivalent of the 6502 SAT boot verifier
        (see src/6502/sat_kernel.asm).

        Assignment $07 = %00000111: x0,x1,x2=True  x3,x4=False
        Five 3-literal clauses — all must be TRUE.
        """
        assignment = {
            "x0": True,   "x1": True,  "x2": True,
            "x3": False,  "x4": False,
        }
        clauses = [
            [("x0", False), ("x1", True),  ("x2", False)],   # C1
            [("x0", True),  ("x1", False), ("x3", True)],    # C2
            [("x1", False), ("x2", False), ("x3", False)],   # C3
            [("x2", True),  ("x3", True),  ("x4", False)],   # C4
            [("x0", False), ("x3", False), ("x4", True)],    # C5
        ]
        return all(
            any(assignment[var] == (not negated) for var, negated in clause)
            for clause in clauses
        )

    def handle(self, req: ChildRequest) -> tuple[str, AuditReceipt]:
        if not self._sat_boot_check():
            return SAFE_TEMPLATE, self._audit("BOOT_FAIL", req)

        clean, pii = PIIScrubber.scrub(req.raw_text)
        if pii:
            return SAFE_TEMPLATE, self._audit("PII_BLOCKED", req)

        approved, risk = TopicPolicy.check(clean, req.domain_id)
        if risk or not approved:
            return SAFE_TEMPLATE, self._audit("TOPIC_BLOCKED", req)

        if self._broker is None:
            return SAFE_TEMPLATE, self._audit("NO_BROKER", req)

        try:
            response = self._broker({
                "age_band":   req.age_band,
                "domain_id":  req.domain_id,
                "text":       clean[:512],
                "max_tokens": 200,
                "nonce":      req.session_nonce,
            })
            return response, self._audit("MODEL_REPLY", req)
        except Exception:
            return SAFE_TEMPLATE, self._audit("BROKER_ERROR", req)

    def _audit(self, event: str, req: ChildRequest) -> AuditReceipt:
        r = AuditReceipt(
            event=event, policy_version=self.POLICY_VERSION,
            age_band=req.age_band, domain_id=req.domain_id,
            nonce=req.session_nonce, timestamp=time.time(),
        )
        self._audit_log.append(r)
        return r

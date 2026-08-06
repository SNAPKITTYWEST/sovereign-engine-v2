"""
Stage 1 + 2: RegexParser + ASTBuilder

RegexParser:  raw input → token stream with intent signals
              Strips dangerous payload tokens BEFORE they enter the AST.

ASTBuilder:   token stream → INVERTED AST
              Tree is inverted so:
                - Structural intent nodes (CODE_INTENT, QUERY_INTENT, CONSTRAINT)
                  are interior nodes with HIGH routing weight
                - Literal payload nodes (WORD, PATH_REF, NUMBER, FUNCTION_REF)
                  are leaves with LOW routing weight (they don't drive routing)

              This means dangerous literals (rm, shell, execute, paths)
              CANNOT propagate routing signal upward — they're dead leaves.

Payload elimination rules:
  1. BLOCKLIST_EXACT  — known dangerous exact tokens → dropped entirely
  2. BLOCKLIST_PATTERN — dangerous patterns (shell ops, path traversal) → dropped
  3. PAYLOAD_TYPES    — token types that become zero-weight leaves in AST
  4. Inverted tree    — payload leaves cannot influence parent routing weights
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any


# ==========================================
# Payload blocklists
# ==========================================

# Exact tokens that are always stripped — never enter the AST
BLOCKLIST_EXACT: frozenset[str] = frozenset({
    # Shell destructive ops
    "rm", "rf", "sudo", "chmod", "chown", "kill", "pkill", "killall",
    "mkfs", "dd", "shred", "truncate", "fdisk", "parted",
    # Code injection / eval
    "eval", "exec", "execfile", "compile", "__import__",
    "subprocess", "popen", "spawn", "system",
    # Network exfil
    "curl", "wget", "nc", "netcat", "nmap", "telnet", "ftp",
    # Privilege escalation
    "su", "passwd", "useradd", "userdel", "visudo",
    # Path traversal tokens
    "..", "~",
})

# Regex patterns that flag a token as dangerous → stripped
BLOCKLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\.\./"),                          # path traversal
    re.compile(r"^/etc/"),                          # system paths
    re.compile(r"^/proc/"),
    re.compile(r"^/sys/"),
    re.compile(r"^/dev/"),
    re.compile(r";.*$"),                            # command chaining
    re.compile(r"\|\s*\w"),                         # pipe injection
    re.compile(r"&&|\|\|"),                         # logical chain
    re.compile(r"`[^`]+`"),                         # backtick execution
    re.compile(r"\$\([^)]+\)"),                     # command substitution
    re.compile(r"0x[0-9a-fA-F]{4,}"),              # hex shellcode
    # XXE / XML injection — if AST ever gets XML tag parsing,
    # these patterns prevent external entity expansion attacks
    re.compile(r"<!ENTITY", re.IGNORECASE),         # XXE entity declaration
    re.compile(r"<!DOCTYPE", re.IGNORECASE),        # DTD injection
    re.compile(r"SYSTEM\s+[\"']", re.IGNORECASE),  # SYSTEM identifier
    re.compile(r"PUBLIC\s+[\"']", re.IGNORECASE),  # PUBLIC identifier
    re.compile(r"file://"),                         # local file URI
    re.compile(r"jar://"),                          # JAR URI
    re.compile(r"php://"),                          # PHP wrapper
    re.compile(r"data:text/"),                      # data URI injection
]

# Token types that become PAYLOAD leaves in the AST (zero routing weight)
# These nodes exist in the tree for traceability but cannot drive routing
PAYLOAD_TYPES: frozenset[str] = frozenset({
    "WORD", "NUMBER", "PATH_REF", "FUNCTION_REF",
})

# Token types that are STRUCTURAL (drive routing)
STRUCTURAL_TYPES: frozenset[str] = frozenset({
    "CODE_INTENT", "QUERY_INTENT", "CONSTRAINT", "OPERATOR",
    "LANGUAGE", "ENTITY",
})


# ==========================================
# Token patterns
# ==========================================

TOKEN_PATTERNS: list[tuple[str, str]] = [
    ("CODE_INTENT",     r"\b(write|implement|create|build|generate|fix|debug|refactor)\b"),
    ("QUERY_INTENT",    r"\b(what|how|why|when|where|explain|describe|list|show)\b"),
    ("CONSTRAINT",      r"\b(must|should|only|never|always|require|ensure|without)\b"),
    ("OPERATOR",        r"\b(and|or|not|if|then|else|given|when|unless)\b"),
    ("LANGUAGE",        r"\b(python|rust|c\+\+|javascript|typescript|haskell|lean|coq|sql)\b"),
    ("ENTITY",          r"\b([A-Z][a-zA-Z0-9]+(?:Manager|Engine|Service|Handler|Parser|Builder|Observer))\b"),
    ("FUNCTION_REF",    r"\b[a-z_][a-z0-9_]*\(\)"),
    ("PATH_REF",        r"[a-zA-Z0-9_/\\.-]+\.[a-zA-Z]{1,6}"),
    ("NUMBER",          r"\b\d+(?:\.\d+)?\b"),
    ("WORD",            r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"),
]

_COMPILED = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in TOKEN_PATTERNS]


# ==========================================
# Data structures
# ==========================================

@dataclass
class Token:
    type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0
    is_payload: bool = False    # True = literal leaf, does not drive routing
    stripped: bool = False      # True = was blocked, not in AST at all


@dataclass
class ASTNode:
    id: int
    type: str
    value: str
    confidence: float           # 0 for payload leaves, >0 for structural nodes
    routing_weight: float       # contribution to routing (0 for payloads)
    span: tuple[int, int]
    children: list[ASTNode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_payload: bool = False    # payload leaf = does not influence routing


@dataclass
class ParseResult:
    tokens: list[Token]
    stripped_tokens: list[Token]    # tokens removed by payload filter
    ast_root: ASTNode
    intent: str
    confidence: float
    signals: dict[str, float]
    payload_blocked: int            # count of stripped tokens


# ==========================================
# Stage 1: RegexParser with payload strip
# ==========================================

class RegexParser:
    """
    Stage 1: Tokenize and strip dangerous payloads.

    Two-pass:
      Pass 1: tokenize raw input
      Pass 2: filter each token through blocklist
               → blocked tokens go into stripped_tokens list
               → clean tokens proceed to ASTBuilder
    """

    def parse(self, text: str) -> tuple[list[Token], list[Token]]:
        """
        Returns (clean_tokens, stripped_tokens).
        clean_tokens  → safe to enter AST
        stripped_tokens → blocked payloads (logged, not processed)
        """
        raw_tokens = self._tokenize(text)
        clean: list[Token] = []
        stripped: list[Token] = []

        for tok in raw_tokens:
            if self._is_blocked(tok.value):
                tok.stripped = True
                stripped.append(tok)
            else:
                if tok.type in PAYLOAD_TYPES:
                    tok.is_payload = True
                clean.append(tok)

        return clean, stripped

    def _tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        pos = 0

        while pos < len(text):
            if text[pos].isspace():
                pos += 1
                continue

            matched = False
            for token_type, pattern in _COMPILED:
                m = pattern.match(text, pos)
                if m:
                    tokens.append(Token(
                        type=token_type,
                        value=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        confidence=1.0
                    ))
                    pos = m.end()
                    matched = True
                    break

            if not matched:
                pos += 1

        return tokens

    def _is_blocked(self, value: str) -> bool:
        lower = value.lower()

        # Exact blocklist
        if lower in BLOCKLIST_EXACT:
            return True

        # Pattern blocklist
        for pattern in BLOCKLIST_PATTERNS:
            if pattern.search(value):
                return True

        return False

    def extract_signals(self, tokens: list[Token]) -> dict[str, float]:
        """
        Extract routing signals from STRUCTURAL tokens only.
        Payload tokens are excluded from signal computation —
        they cannot inflate or deflate routing weights.
        """
        structural = [t for t in tokens if not t.is_payload and not t.stripped]
        total = len(structural) or 1

        type_counts: dict[str, int] = {}
        for tok in structural:
            type_counts[tok.type] = type_counts.get(tok.type, 0) + 1

        return {
            "code_signal":       type_counts.get("CODE_INTENT", 0) / total,
            "query_signal":      type_counts.get("QUERY_INTENT", 0) / total,
            "constraint_signal": type_counts.get("CONSTRAINT", 0) / total,
            "operator_signal":   type_counts.get("OPERATOR", 0) / total,
            "language_signal":   type_counts.get("LANGUAGE", 0) / total,
            "entity_signal":     type_counts.get("ENTITY", 0) / total,
        }


# ==========================================
# Stage 2: ASTBuilder — inverted tree
# ==========================================

class ASTBuilder:
    """
    Stage 2: Build INVERTED AST from clean token stream.

    Inverted tree structure:
      ROOT (intent)
        └── STRUCTURAL nodes (CODE_INTENT, CONSTRAINT, etc.)   ← routing weight 1.0
              └── PAYLOAD leaves (WORD, PATH_REF, etc.)        ← routing weight 0.0

    Key invariant:
      Routing weight flows DOWNWARD only.
      Payload leaves CANNOT propagate weight back to parent nodes.
      The symbolic graph respects this: edges from payload→structural have weight 0.
      Only structural→structural and structural→payload edges carry weight.

    Why "inverted":
      Normal NLP parse trees put literals at leaves and abstract nodes at root.
      We go further — we explicitly zero-weight the leaves so they cannot
      influence the routing decision even if they appear in the graph.
      Dangerous tokens (rm, shell) become inert leaves with routing_weight=0.
    """

    def __init__(self):
        self._id_counter = 0

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def build(self, tokens: list[Token], signals: dict[str, float]) -> ASTNode:
        intent = self._classify_intent(signals)

        root = ASTNode(
            id=self._next_id(),
            type="ROOT",
            value=intent,
            confidence=max(signals.values()) if signals else 0.5,
            routing_weight=1.0,
            span=(0, 0),
            metadata={"signals": signals}
        )

        current_structural: ASTNode | None = None

        for tok in tokens:
            if tok.stripped:
                continue  # already blocked

            is_payload = tok.type in PAYLOAD_TYPES

            node = ASTNode(
                id=self._next_id(),
                type=tok.type,
                value=tok.value,
                # Payload leaves get ZERO confidence and routing_weight
                confidence=0.0 if is_payload else tok.confidence,
                routing_weight=0.0 if is_payload else 1.0,
                span=(tok.start, tok.end),
                is_payload=is_payload,
                metadata={"is_payload": is_payload}
            )

            if tok.type in ("CODE_INTENT", "QUERY_INTENT"):
                root.children.append(node)
                current_structural = node

            elif tok.type == "CONSTRAINT":
                node.metadata["is_constraint"] = True
                target = current_structural if current_structural else root
                target.children.append(node)

            elif tok.type == "OPERATOR":
                node.metadata["is_operator"] = True
                target = current_structural if current_structural else root
                target.children.append(node)

            elif tok.type in ("LANGUAGE", "ENTITY"):
                # Structural modifiers — attach to current action, non-zero weight
                target = current_structural if current_structural else root
                target.children.append(node)

            else:
                # PAYLOAD leaf — attach as inert child
                node.is_payload = True
                node.routing_weight = 0.0
                node.confidence = 0.0
                target = current_structural if current_structural else root
                target.children.append(node)

        return root

    def _classify_intent(self, signals: dict[str, float]) -> str:
        code_w = signals.get("code_signal", 0)
        query_w = signals.get("query_signal", 0)
        constraint_w = signals.get("constraint_signal", 0)

        if code_w > query_w and code_w > constraint_w:
            return "code"
        elif query_w > code_w and query_w > constraint_w:
            return "query"
        elif constraint_w > 0.1:
            return "constraint"
        else:
            return "mixed"

    def full_parse(self, text: str) -> ParseResult:
        parser = RegexParser()
        clean_tokens, stripped_tokens = parser.parse(text)
        signals = parser.extract_signals(clean_tokens)
        ast_root = self.build(clean_tokens, signals)
        intent = ast_root.value
        confidence = sum(signals.values()) / max(len(signals), 1)

        return ParseResult(
            tokens=clean_tokens,
            stripped_tokens=stripped_tokens,
            ast_root=ast_root,
            intent=intent,
            confidence=confidence,
            signals=signals,
            payload_blocked=len(stripped_tokens)
        )

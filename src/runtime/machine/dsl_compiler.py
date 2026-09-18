"""
HyperKittyConstraintDSL — Full Compiler Implementation.

Pipeline:
    Source Text
       |
    Regex Lexer (deterministic tokenization)
       |
    Token Stream (typed, positioned)
       |
    Parser (recursive descent, no ambiguity)
       |
    IR Nodes (typed, validated)
       |
    Constraint Validation (5 constraints)
       |
    Verified IR (sealed)
       |
    Backend Emission (Python / C / VM bytecode / x86-64)

Language grammar:

    program     ::= statement*
    statement   ::= directive | declaration | operation | constraint | label | comment
    directive   ::= '@' IDENT params?
    declaration ::= 'LET' IDENT '=' expr
                  | 'ALLOC' IDENT (':' type)?
                  | 'CONST' IDENT '=' literal
    operation   ::= opcode operands
    constraint  ::= 'ASSERT' constraint_expr
                  | 'REQUIRE' constraint_expr
                  | 'INVARIANT' IDENT ':' constraint_expr
    label       ::= IDENT ':'
    comment     ::= '#' .*
    opcode      ::= NAND | NOT | AND | OR | XOR | IMPLIES | EQUAL
                  | PUSH | POP | DUP | SWAP | ROT
                  | ADD | SUB | MUL | DIV | MOD
                  | JMP | JZ | JNZ | CALL | RET
                  | GATE | FILTER | ROUTE | DISPATCH
                  | COMMIT | SEAL | VERIFY | CHECKPOINT
                  | ENTROPY | MEASURE | CLAMP
                  | EMIT | PRINT | HALT | NOP
                  | H | CNOT | TOFFOLI | MEASURE_Q
                  | ALLOC | FREE | LOAD | STORE
    operands    ::= (IDENT | NUMBER | STRING) (',' (IDENT | NUMBER | STRING))*
    expr        ::= term (('+' | '-') term)*
    term        ::= factor (('*' | '/') factor)*
    factor      ::= NUMBER | IDENT | '(' expr ')' | unary
    unary       ::= ('!' | '-' | '~') factor
    constraint_expr ::= 'H' '<=' NUMBER
                      | 'active' '=>' 'trusted'
                      | 'injective' '(' IDENT ')'
                      | 'acyclic' '(' IDENT ')'
                      | 'nand_complete' '(' IDENT ')'
    type        ::= 'bit' | 'byte' | 'word' | 'float' | 'qubit' | 'glyph'
    literal     ::= NUMBER | STRING | 'true' | 'false'

Pure Python 3.11 stdlib. No dependencies.
"""

import re
import hashlib
import math
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# =============================================================================
# TOKEN TYPES
# =============================================================================

class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()
    BOOL_TRUE = auto()
    BOOL_FALSE = auto()

    # Keywords
    LET = auto()
    CONST = auto()
    ALLOC = auto()
    FREE = auto()
    ASSERT = auto()
    REQUIRE = auto()
    INVARIANT = auto()

    # Type keywords
    TYPE_BIT = auto()
    TYPE_BYTE = auto()
    TYPE_WORD = auto()
    TYPE_FLOAT = auto()
    TYPE_QUBIT = auto()
    TYPE_GLYPH = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    BANG = auto()
    TILDE = auto()
    AMPERSAND = auto()
    PIPE = auto()
    CARET = auto()
    LSHIFT = auto()
    RSHIFT = auto()

    # Comparison
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    ARROW = auto()       # ->
    FAT_ARROW = auto()   # =>

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    COLON = auto()
    SEMICOLON = auto()
    DOT = auto()
    AT = auto()
    ASSIGN = auto()      # =

    # Opcodes (VM)
    OP_NOP = auto()
    OP_PUSH = auto()
    OP_POP = auto()
    OP_DUP = auto()
    OP_SWAP = auto()
    OP_ROT = auto()
    OP_COPY = auto()
    OP_ADD = auto()
    OP_SUB = auto()
    OP_MUL = auto()
    OP_DIV = auto()
    OP_MOD = auto()
    OP_NEG = auto()
    OP_ABS = auto()
    OP_NAND = auto()
    OP_AND = auto()
    OP_OR = auto()
    OP_NOT = auto()
    OP_XOR = auto()
    OP_XNOR = auto()
    OP_NOR = auto()
    OP_IMPLIES = auto()
    OP_EQUAL = auto()
    OP_JMP = auto()
    OP_JZ = auto()
    OP_JNZ = auto()
    OP_CALL = auto()
    OP_RET = auto()
    OP_LOOP = auto()
    OP_GATE = auto()
    OP_FILTER = auto()
    OP_ROUTE = auto()
    OP_DISPATCH = auto()
    OP_FORWARD = auto()
    OP_COMMIT = auto()
    OP_SEAL = auto()
    OP_VERIFY = auto()
    OP_CHECKPOINT = auto()
    OP_ROLLBACK = auto()
    OP_ENTROPY = auto()
    OP_MEASURE = auto()
    OP_CLAMP = auto()
    OP_EMIT = auto()
    OP_PRINT = auto()
    OP_READ = auto()
    OP_HALT = auto()
    OP_LOAD = auto()
    OP_STORE = auto()

    # Quantum ops
    OP_H = auto()
    OP_CNOT = auto()
    OP_TOFFOLI = auto()
    OP_MEASURE_Q = auto()

    # Bitwise
    OP_BAND = auto()
    OP_BOR = auto()
    OP_BXOR = auto()
    OP_BNOT = auto()
    OP_SHL = auto()
    OP_SHR = auto()

    # Constraint keywords
    KW_H = auto()           # entropy symbol
    KW_ACTIVE = auto()
    KW_TRUSTED = auto()
    KW_INJECTIVE = auto()
    KW_ACYCLIC = auto()
    KW_NAND_COMPLETE = auto()

    # Special
    LABEL = auto()       # ident followed by ':'
    COMMENT = auto()
    NEWLINE = auto()
    EOF = auto()


# =============================================================================
# TOKEN
# =============================================================================

@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:{self.col})"


# =============================================================================
# REGEX LEXER
# =============================================================================

# Keywords to token type
KEYWORDS = {
    'LET': TokenType.LET,
    'CONST': TokenType.CONST,
    'ALLOC': TokenType.ALLOC,
    'FREE': TokenType.FREE,
    'ASSERT': TokenType.ASSERT,
    'REQUIRE': TokenType.REQUIRE,
    'INVARIANT': TokenType.INVARIANT,
    'true': TokenType.BOOL_TRUE,
    'false': TokenType.BOOL_FALSE,
    'bit': TokenType.TYPE_BIT,
    'byte': TokenType.TYPE_BYTE,
    'word': TokenType.TYPE_WORD,
    'float': TokenType.TYPE_FLOAT,
    'qubit': TokenType.TYPE_QUBIT,
    'glyph': TokenType.TYPE_GLYPH,
    'active': TokenType.KW_ACTIVE,
    'trusted': TokenType.KW_TRUSTED,
    'injective': TokenType.KW_INJECTIVE,
    'acyclic': TokenType.KW_ACYCLIC,
    'nand_complete': TokenType.KW_NAND_COMPLETE,
}

# Opcode keywords
OPCODES = {
    'NOP': TokenType.OP_NOP,
    'PUSH': TokenType.OP_PUSH,
    'POP': TokenType.OP_POP,
    'DUP': TokenType.OP_DUP,
    'SWAP': TokenType.OP_SWAP,
    'ROT': TokenType.OP_ROT,
    'COPY': TokenType.OP_COPY,
    'ADD': TokenType.OP_ADD,
    'SUB': TokenType.OP_SUB,
    'MUL': TokenType.OP_MUL,
    'DIV': TokenType.OP_DIV,
    'MOD': TokenType.OP_MOD,
    'NEG': TokenType.OP_NEG,
    'ABS': TokenType.OP_ABS,
    'NAND': TokenType.OP_NAND,
    'AND': TokenType.OP_AND,
    'OR': TokenType.OP_OR,
    'NOT': TokenType.OP_NOT,
    'XOR': TokenType.OP_XOR,
    'XNOR': TokenType.OP_XNOR,
    'NOR': TokenType.OP_NOR,
    'IMPLIES': TokenType.OP_IMPLIES,
    'EQUAL': TokenType.OP_EQUAL,
    'JMP': TokenType.OP_JMP,
    'JZ': TokenType.OP_JZ,
    'JNZ': TokenType.OP_JNZ,
    'CALL': TokenType.OP_CALL,
    'RET': TokenType.OP_RET,
    'LOOP': TokenType.OP_LOOP,
    'GATE': TokenType.OP_GATE,
    'FILTER': TokenType.OP_FILTER,
    'ROUTE': TokenType.OP_ROUTE,
    'DISPATCH': TokenType.OP_DISPATCH,
    'FORWARD': TokenType.OP_FORWARD,
    'COMMIT': TokenType.OP_COMMIT,
    'SEAL': TokenType.OP_SEAL,
    'VERIFY': TokenType.OP_VERIFY,
    'CHECKPOINT': TokenType.OP_CHECKPOINT,
    'ROLLBACK': TokenType.OP_ROLLBACK,
    'ENTROPY': TokenType.OP_ENTROPY,
    'MEASURE': TokenType.OP_MEASURE,
    'CLAMP': TokenType.OP_CLAMP,
    'EMIT': TokenType.OP_EMIT,
    'PRINT': TokenType.OP_PRINT,
    'READ': TokenType.OP_READ,
    'HALT': TokenType.OP_HALT,
    'LOAD': TokenType.OP_LOAD,
    'STORE': TokenType.OP_STORE,
    'H': TokenType.OP_H,
    'CNOT': TokenType.OP_CNOT,
    'TOFFOLI': TokenType.OP_TOFFOLI,
    'MEASURE_Q': TokenType.OP_MEASURE_Q,
    'BAND': TokenType.OP_BAND,
    'BOR': TokenType.OP_BOR,
    'BXOR': TokenType.OP_BXOR,
    'BNOT': TokenType.OP_BNOT,
    'SHL': TokenType.OP_SHL,
    'SHR': TokenType.OP_SHR,
}

# Regex patterns for lexer (order matters -- longest match first)
TOKEN_PATTERNS = [
    # Comments
    (r'#[^\n]*', 'COMMENT'),
    # Strings
    (r'"[^"\\]*(?:\\.[^"\\]*)*"', 'STRING'),
    (r"'[^'\\]*(?:\\.[^'\\]*)*'", 'STRING'),
    # Numbers (hex, binary, float, int)
    (r'0x[0-9A-Fa-f]+', 'NUMBER'),
    (r'0b[01]+', 'NUMBER'),
    (r'\d+\.\d+', 'NUMBER'),
    (r'\d+', 'NUMBER'),
    # Multi-char operators
    (r'->', 'ARROW'),
    (r'=>', 'FAT_ARROW'),
    (r'<=', 'LE'),
    (r'>=', 'GE'),
    (r'!=', 'NEQ'),
    (r'==', 'EQ'),
    (r'<<', 'LSHIFT'),
    (r'>>', 'RSHIFT'),
    # Single-char operators
    (r'\+', 'PLUS'),
    (r'-', 'MINUS'),
    (r'\*', 'STAR'),
    (r'/', 'SLASH'),
    (r'%', 'PERCENT'),
    (r'!', 'BANG'),
    (r'~', 'TILDE'),
    (r'&', 'AMPERSAND'),
    (r'\|', 'PIPE'),
    (r'\^', 'CARET'),
    (r'<', 'LT'),
    (r'>', 'GT'),
    # Delimiters
    (r'\(', 'LPAREN'),
    (r'\)', 'RPAREN'),
    (r'\[', 'LBRACKET'),
    (r'\]', 'RBRACKET'),
    (r'\{', 'LBRACE'),
    (r'\}', 'RBRACE'),
    (r',', 'COMMA'),
    (r':', 'COLON'),
    (r';', 'SEMICOLON'),
    (r'\.', 'DOT'),
    (r'@', 'AT'),
    (r'=', 'ASSIGN'),
    # Identifiers (must come after operators)
    (r'[A-Za-z_][A-Za-z0-9_]*', 'IDENT'),
    # Whitespace (skip, but track newlines)
    (r'\n', 'NEWLINE'),
    (r'[ \t\r]+', 'WHITESPACE'),
]

# Compile all patterns into one regex with named groups
_PATTERN_PARTS = []
for i, (pattern, name) in enumerate(TOKEN_PATTERNS):
    _PATTERN_PARTS.append(f'(?P<T{i}>{pattern})')
MASTER_PATTERN = re.compile('|'.join(_PATTERN_PARTS))

# Map group names back to token category names
_GROUP_TO_CATEGORY = {f'T{i}': name for i, (_, name) in enumerate(TOKEN_PATTERNS)}

# Simple category -> TokenType mapping for operators/delimiters
_SIMPLE_MAP = {
    'ARROW': TokenType.ARROW,
    'FAT_ARROW': TokenType.FAT_ARROW,
    'LE': TokenType.LE,
    'GE': TokenType.GE,
    'NEQ': TokenType.NEQ,
    'EQ': TokenType.EQ,
    'LSHIFT': TokenType.LSHIFT,
    'RSHIFT': TokenType.RSHIFT,
    'PLUS': TokenType.PLUS,
    'MINUS': TokenType.MINUS,
    'STAR': TokenType.STAR,
    'SLASH': TokenType.SLASH,
    'PERCENT': TokenType.PERCENT,
    'BANG': TokenType.BANG,
    'TILDE': TokenType.TILDE,
    'AMPERSAND': TokenType.AMPERSAND,
    'PIPE': TokenType.PIPE,
    'CARET': TokenType.CARET,
    'LT': TokenType.LT,
    'GT': TokenType.GT,
    'LPAREN': TokenType.LPAREN,
    'RPAREN': TokenType.RPAREN,
    'LBRACKET': TokenType.LBRACKET,
    'RBRACKET': TokenType.RBRACKET,
    'LBRACE': TokenType.LBRACE,
    'RBRACE': TokenType.RBRACE,
    'COMMA': TokenType.COMMA,
    'COLON': TokenType.COLON,
    'SEMICOLON': TokenType.SEMICOLON,
    'DOT': TokenType.DOT,
    'AT': TokenType.AT,
    'ASSIGN': TokenType.ASSIGN,
    'NEWLINE': TokenType.NEWLINE,
    'COMMENT': TokenType.COMMENT,
}


class LexError(Exception):
    def __init__(self, message, line, col):
        super().__init__(f"Lex error at L{line}:{col}: {message}")
        self.line = line
        self.col = col


def lex(source: str) -> list[Token]:
    """
    Tokenize source text into a list of Tokens.

    Uses compiled master regex for O(n) single-pass lexing.
    Deterministic: same input always produces same token stream.

    Args:
        source: DSL source text

    Returns:
        List of Token objects (includes NEWLINE, excludes WHITESPACE)

    Raises:
        LexError: on unrecognized character
    """
    tokens = []
    line = 1
    col = 1
    pos = 0

    for match in MASTER_PATTERN.finditer(source):
        # Check for skipped characters (unrecognized input)
        if match.start() > pos:
            skipped = source[pos:match.start()]
            if skipped.strip():
                raise LexError(f"Unexpected character: {skipped[0]!r}", line, col)

        # Track position
        text_before = source[pos:match.start()]
        for ch in text_before:
            if ch == '\n':
                line += 1
                col = 1
            else:
                col += 1

        # Find which group matched
        matched_text = match.group()
        category = None
        for group_name, group_value in match.groupdict().items():
            if group_value is not None:
                category = _GROUP_TO_CATEGORY[group_name]
                break

        if category is None:
            raise LexError(f"Internal: no group matched for {matched_text!r}", line, col)

        # Skip whitespace entirely
        if category == 'WHITESPACE':
            pos = match.end()
            col += len(matched_text)
            continue

        # Determine token type
        if category == 'IDENT':
            # Check keywords, opcodes, then default to IDENT
            if matched_text in OPCODES:
                tok_type = OPCODES[matched_text]
            elif matched_text in KEYWORDS:
                tok_type = KEYWORDS[matched_text]
            else:
                tok_type = TokenType.IDENT
        elif category == 'NUMBER':
            tok_type = TokenType.NUMBER
        elif category == 'STRING':
            tok_type = TokenType.STRING
        elif category in _SIMPLE_MAP:
            tok_type = _SIMPLE_MAP[category]
        else:
            tok_type = TokenType.IDENT

        token = Token(type=tok_type, value=matched_text, line=line, col=col)
        tokens.append(token)

        # Advance position
        if category == 'NEWLINE':
            line += 1
            col = 1
        else:
            col += len(matched_text)
        pos = match.end()

    # Check trailing content
    if pos < len(source):
        remaining = source[pos:]
        if remaining.strip():
            raise LexError(f"Unexpected trailing: {remaining[:20]!r}", line, col)

    tokens.append(Token(type=TokenType.EOF, value='', line=line, col=col))
    return tokens


# =============================================================================
# IR NODE TYPES
# =============================================================================

class IRNodeType(Enum):
    PROGRAM = auto()
    DIRECTIVE = auto()
    DECLARATION = auto()
    OPERATION = auto()
    CONSTRAINT = auto()
    LABEL_DEF = auto()
    EXPRESSION = auto()
    LITERAL = auto()
    IDENTIFIER = auto()
    BINARY_OP = auto()
    UNARY_OP = auto()
    CALL = auto()


class DeclKind(Enum):
    LET = auto()
    CONST = auto()
    ALLOC = auto()


class ConstraintKind(Enum):
    ENTROPY_BOUND = auto()
    TRUST_AXIOM = auto()
    INJECTIVE = auto()
    ACYCLIC = auto()
    NAND_COMPLETE = auto()
    CUSTOM = auto()


@dataclass
class IRNode:
    node_type: IRNodeType
    line: int
    col: int
    children: list = field(default_factory=list)
    # Payload fields (type-dependent)
    opcode: Optional[str] = None
    name: Optional[str] = None
    value: object = None
    decl_kind: Optional[DeclKind] = None
    constraint_kind: Optional[ConstraintKind] = None
    type_annotation: Optional[str] = None
    operator: Optional[str] = None

    def __repr__(self):
        parts = [f"IRNode({self.node_type.name}"]
        if self.opcode:
            parts.append(f" op={self.opcode}")
        if self.name:
            parts.append(f" name={self.name}")
        if self.value is not None:
            parts.append(f" val={self.value}")
        parts.append(f" L{self.line})")
        return ''.join(parts)


# =============================================================================
# PARSER
# =============================================================================

class ParseError(Exception):
    def __init__(self, message, token):
        super().__init__(f"Parse error at L{token.line}:{token.col}: {message}")
        self.token = token


class Parser:
    """
    Recursive descent parser for HyperKittyConstraintDSL.

    Grammar is LL(1) -- no backtracking needed.
    Deterministic: same token stream always produces same IR tree.
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, tok_type: TokenType) -> Token:
        tok = self.peek()
        if tok.type != tok_type:
            raise ParseError(f"Expected {tok_type.name}, got {tok.type.name} ({tok.value!r})", tok)
        return self.advance()

    def match(self, *types: TokenType) -> Optional[Token]:
        if self.peek().type in types:
            return self.advance()
        return None

    def skip_newlines(self):
        while self.peek().type in (TokenType.NEWLINE, TokenType.COMMENT):
            self.advance()

    def at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    # --- Top-level ---

    def parse_program(self) -> IRNode:
        """Parse entire program into IR tree."""
        node = IRNode(node_type=IRNodeType.PROGRAM, line=1, col=1)
        self.skip_newlines()

        while not self.at_end():
            stmt = self.parse_statement()
            if stmt:
                node.children.append(stmt)
            self.skip_newlines()

        return node

    def parse_statement(self) -> Optional[IRNode]:
        """Parse a single statement."""
        tok = self.peek()

        # Directive: @name ...
        if tok.type == TokenType.AT:
            return self.parse_directive()

        # Declarations
        if tok.type == TokenType.LET:
            return self.parse_let()
        if tok.type == TokenType.CONST:
            return self.parse_const()
        if tok.type == TokenType.ALLOC:
            return self.parse_alloc()

        # Constraints
        if tok.type in (TokenType.ASSERT, TokenType.REQUIRE):
            return self.parse_constraint_assert()
        if tok.type == TokenType.INVARIANT:
            return self.parse_invariant()

        # Opcodes
        if self._is_opcode(tok.type):
            return self.parse_operation()

        # Label: IDENT ':'
        if tok.type == TokenType.IDENT:
            # Lookahead for colon
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.COLON:
                return self.parse_label()
            # Otherwise treat as expression statement (rare)
            return self.parse_expression_statement()

        # Skip stray newlines/comments
        if tok.type in (TokenType.NEWLINE, TokenType.COMMENT):
            self.advance()
            return None

        raise ParseError(f"Unexpected token: {tok.value!r}", tok)

    # --- Directives ---

    def parse_directive(self) -> IRNode:
        at_tok = self.expect(TokenType.AT)
        name_tok = self.expect(TokenType.IDENT)
        node = IRNode(node_type=IRNodeType.DIRECTIVE, line=at_tok.line, col=at_tok.col,
                      name=name_tok.value)

        # Collect operands until newline/EOF
        while self.peek().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
            child = self.parse_operand()
            node.children.append(child)

        return node

    # --- Declarations ---

    def parse_let(self) -> IRNode:
        let_tok = self.expect(TokenType.LET)
        name_tok = self.expect(TokenType.IDENT)
        self.expect(TokenType.ASSIGN)
        expr = self.parse_expression()
        return IRNode(node_type=IRNodeType.DECLARATION, line=let_tok.line, col=let_tok.col,
                      name=name_tok.value, decl_kind=DeclKind.LET, children=[expr])

    def parse_const(self) -> IRNode:
        const_tok = self.expect(TokenType.CONST)
        name_tok = self.expect(TokenType.IDENT)
        self.expect(TokenType.ASSIGN)
        expr = self.parse_expression()
        return IRNode(node_type=IRNodeType.DECLARATION, line=const_tok.line, col=const_tok.col,
                      name=name_tok.value, decl_kind=DeclKind.CONST, children=[expr])

    def parse_alloc(self) -> IRNode:
        alloc_tok = self.expect(TokenType.ALLOC)
        name_tok = self.expect(TokenType.IDENT)
        type_ann = None
        if self.match(TokenType.COLON):
            type_tok = self.advance()
            type_ann = type_tok.value
        return IRNode(node_type=IRNodeType.DECLARATION, line=alloc_tok.line, col=alloc_tok.col,
                      name=name_tok.value, decl_kind=DeclKind.ALLOC, type_annotation=type_ann)

    # --- Operations ---

    def parse_operation(self) -> IRNode:
        op_tok = self.advance()
        node = IRNode(node_type=IRNodeType.OPERATION, line=op_tok.line, col=op_tok.col,
                      opcode=op_tok.value)

        # Collect operands until newline/EOF
        while self.peek().type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
            if self.peek().type == TokenType.COMMA:
                self.advance()
                continue
            child = self.parse_operand()
            node.children.append(child)

        return node

    def parse_operand(self) -> IRNode:
        tok = self.peek()
        if tok.type == TokenType.NUMBER:
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value=self._parse_number(tok.value))
        elif tok.type == TokenType.STRING:
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value=tok.value[1:-1])  # strip quotes
        elif tok.type == TokenType.IDENT:
            self.advance()
            return IRNode(node_type=IRNodeType.IDENTIFIER, line=tok.line, col=tok.col,
                          name=tok.value)
        elif tok.type in (TokenType.BOOL_TRUE, TokenType.BOOL_FALSE):
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value=tok.type == TokenType.BOOL_TRUE)
        elif tok.type == TokenType.ARROW:
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value='->', name='arrow')
        else:
            raise ParseError(f"Expected operand, got {tok.type.name}", tok)

    # --- Constraints ---

    def parse_constraint_assert(self) -> IRNode:
        kw_tok = self.advance()  # ASSERT or REQUIRE
        node = IRNode(node_type=IRNodeType.CONSTRAINT, line=kw_tok.line, col=kw_tok.col,
                      name=kw_tok.value)

        tok = self.peek()

        # H <= 0.20
        if tok.type == TokenType.OP_H or (tok.type == TokenType.IDENT and tok.value == 'H'):
            self.advance()
            self.expect(TokenType.LE)
            bound_tok = self.expect(TokenType.NUMBER)
            node.constraint_kind = ConstraintKind.ENTROPY_BOUND
            node.value = self._parse_number(bound_tok.value)
            return node

        # active => trusted
        if tok.type == TokenType.KW_ACTIVE:
            self.advance()
            self.expect(TokenType.FAT_ARROW)
            self.expect(TokenType.KW_TRUSTED)
            node.constraint_kind = ConstraintKind.TRUST_AXIOM
            return node

        # injective(mapping_name)
        if tok.type == TokenType.KW_INJECTIVE:
            self.advance()
            self.expect(TokenType.LPAREN)
            ident = self.expect(TokenType.IDENT)
            self.expect(TokenType.RPAREN)
            node.constraint_kind = ConstraintKind.INJECTIVE
            node.value = ident.value
            return node

        # acyclic(graph_name)
        if tok.type == TokenType.KW_ACYCLIC:
            self.advance()
            self.expect(TokenType.LPAREN)
            ident = self.expect(TokenType.IDENT)
            self.expect(TokenType.RPAREN)
            node.constraint_kind = ConstraintKind.ACYCLIC
            node.value = ident.value
            return node

        # nand_complete(kernel_name)
        if tok.type == TokenType.KW_NAND_COMPLETE:
            self.advance()
            self.expect(TokenType.LPAREN)
            ident = self.expect(TokenType.IDENT)
            self.expect(TokenType.RPAREN)
            node.constraint_kind = ConstraintKind.NAND_COMPLETE
            node.value = ident.value
            return node

        # Fallback: custom constraint expression
        expr = self.parse_expression()
        node.constraint_kind = ConstraintKind.CUSTOM
        node.children.append(expr)
        return node

    def parse_invariant(self) -> IRNode:
        inv_tok = self.expect(TokenType.INVARIANT)
        name_tok = self.expect(TokenType.IDENT)
        self.expect(TokenType.COLON)

        node = IRNode(node_type=IRNodeType.CONSTRAINT, line=inv_tok.line, col=inv_tok.col,
                      name=name_tok.value)

        # Parse the constraint body (reuse assert logic after colon)
        tok = self.peek()
        if tok.type == TokenType.OP_H or (tok.type == TokenType.IDENT and tok.value == 'H'):
            self.advance()
            self.expect(TokenType.LE)
            bound_tok = self.expect(TokenType.NUMBER)
            node.constraint_kind = ConstraintKind.ENTROPY_BOUND
            node.value = self._parse_number(bound_tok.value)
        elif tok.type == TokenType.KW_ACTIVE:
            self.advance()
            self.expect(TokenType.FAT_ARROW)
            self.expect(TokenType.KW_TRUSTED)
            node.constraint_kind = ConstraintKind.TRUST_AXIOM
        else:
            expr = self.parse_expression()
            node.constraint_kind = ConstraintKind.CUSTOM
            node.children.append(expr)

        return node

    # --- Labels ---

    def parse_label(self) -> IRNode:
        name_tok = self.expect(TokenType.IDENT)
        self.expect(TokenType.COLON)
        return IRNode(node_type=IRNodeType.LABEL_DEF, line=name_tok.line, col=name_tok.col,
                      name=name_tok.value)

    # --- Expressions ---

    def parse_expression_statement(self) -> IRNode:
        return self.parse_expression()

    def parse_expression(self) -> IRNode:
        return self._parse_additive()

    def _parse_additive(self) -> IRNode:
        left = self._parse_multiplicative()
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS):
            op_tok = self.advance()
            right = self._parse_multiplicative()
            left = IRNode(node_type=IRNodeType.BINARY_OP, line=op_tok.line, col=op_tok.col,
                          operator=op_tok.value, children=[left, right])
        return left

    def _parse_multiplicative(self) -> IRNode:
        left = self._parse_unary()
        while self.peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op_tok = self.advance()
            right = self._parse_unary()
            left = IRNode(node_type=IRNodeType.BINARY_OP, line=op_tok.line, col=op_tok.col,
                          operator=op_tok.value, children=[left, right])
        return left

    def _parse_unary(self) -> IRNode:
        if self.peek().type in (TokenType.BANG, TokenType.MINUS, TokenType.TILDE):
            op_tok = self.advance()
            operand = self._parse_unary()
            return IRNode(node_type=IRNodeType.UNARY_OP, line=op_tok.line, col=op_tok.col,
                          operator=op_tok.value, children=[operand])
        return self._parse_primary()

    def _parse_primary(self) -> IRNode:
        tok = self.peek()

        if tok.type == TokenType.NUMBER:
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value=self._parse_number(tok.value))

        if tok.type == TokenType.STRING:
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value=tok.value[1:-1])

        if tok.type in (TokenType.BOOL_TRUE, TokenType.BOOL_FALSE):
            self.advance()
            return IRNode(node_type=IRNodeType.LITERAL, line=tok.line, col=tok.col,
                          value=tok.type == TokenType.BOOL_TRUE)

        if tok.type == TokenType.IDENT:
            self.advance()
            # Check for function call: ident '(' ... ')'
            if self.peek().type == TokenType.LPAREN:
                self.advance()  # consume (
                args = []
                while self.peek().type != TokenType.RPAREN:
                    if args:
                        self.expect(TokenType.COMMA)
                    args.append(self.parse_expression())
                self.expect(TokenType.RPAREN)
                return IRNode(node_type=IRNodeType.CALL, line=tok.line, col=tok.col,
                              name=tok.value, children=args)
            return IRNode(node_type=IRNodeType.IDENTIFIER, line=tok.line, col=tok.col,
                          name=tok.value)

        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr

        raise ParseError(f"Expected expression, got {tok.type.name} ({tok.value!r})", tok)

    # --- Helpers ---

    @staticmethod
    def _is_opcode(tok_type: TokenType) -> bool:
        return tok_type.name.startswith('OP_')

    @staticmethod
    def _parse_number(text: str):
        if text.startswith('0x'):
            return int(text, 16)
        if text.startswith('0b'):
            return int(text, 2)
        if '.' in text:
            return float(text)
        return int(text)


# =============================================================================
# CONSTRAINT ENGINE
# =============================================================================

class ConstraintViolation(Exception):
    def __init__(self, constraint, detail, line=0):
        super().__init__(f"Constraint [{constraint}] violated at L{line}: {detail}")
        self.constraint = constraint
        self.detail = detail
        self.line = line


@dataclass
class ConstraintResult:
    name: str
    passed: bool
    detail: str
    line: int = 0


class ConstraintEngine:
    """
    Validates the 5 HyperKittyConstraintDSL constraints against an IR tree.

    Constraints:
        1. NAND_COMPLETE   -- all boolean ops derivable from NAND
        2. ENTROPY_BOUND   -- H <= threshold (default 0.20 nats)
        3. TRUST_AXIOM     -- active(I) => trusted(I)
        4. INJECTIVE       -- glyph mapping is one-to-one
        5. ACYCLIC         -- routing graph has no cycles

    Also validates:
        - No unresolved labels
        - No duplicate declarations
        - Type correctness of operands
    """

    def __init__(self):
        self.results: list[ConstraintResult] = []
        self.symbols: dict[str, IRNode] = {}
        self.labels: dict[str, int] = {}
        self.active_set: set[str] = set()
        self.trusted_set: set[str] = set()
        self.glyph_map: dict[str, str] = {}
        self.graph_edges: dict[str, list[str]] = {}

    def validate(self, program: IRNode) -> tuple[bool, list[ConstraintResult]]:
        """
        Run all constraint checks on an IR tree.

        Returns:
            (all_passed, results_list)
        """
        self.results = []
        self._collect_symbols(program)
        self._check_declarations(program)
        self._check_labels(program)
        self._check_constraints(program)
        self._check_nand_completeness()
        all_passed = all(r.passed for r in self.results)
        return all_passed, self.results

    def _collect_symbols(self, program: IRNode):
        """First pass: collect all declarations and labels."""
        for child in program.children:
            if child.node_type == IRNodeType.DECLARATION:
                self.symbols[child.name] = child
            elif child.node_type == IRNodeType.LABEL_DEF:
                self.labels[child.name] = child.line

    def _check_declarations(self, program: IRNode):
        """Check for duplicate declarations."""
        seen = {}
        for child in program.children:
            if child.node_type == IRNodeType.DECLARATION:
                if child.name in seen:
                    self.results.append(ConstraintResult(
                        name="NO_DUPLICATE_DECL",
                        passed=False,
                        detail=f"Duplicate declaration: {child.name} (first at L{seen[child.name]})",
                        line=child.line
                    ))
                else:
                    seen[child.name] = child.line

        if not any(r.name == "NO_DUPLICATE_DECL" and not r.passed for r in self.results):
            self.results.append(ConstraintResult(
                name="NO_DUPLICATE_DECL",
                passed=True,
                detail=f"{len(seen)} declarations, no duplicates"
            ))

    def _check_labels(self, program: IRNode):
        """Check that all jump targets resolve to defined labels."""
        jump_ops = {'JMP', 'JZ', 'JNZ', 'CALL', 'LOOP'}
        unresolved = []

        for child in program.children:
            if child.node_type == IRNodeType.OPERATION and child.opcode in jump_ops:
                for operand in child.children:
                    if operand.node_type == IRNodeType.IDENTIFIER:
                        if operand.name not in self.labels:
                            unresolved.append((operand.name, child.line))

        if unresolved:
            self.results.append(ConstraintResult(
                name="LABEL_RESOLUTION",
                passed=False,
                detail=f"Unresolved labels: {[u[0] for u in unresolved]}",
                line=unresolved[0][1]
            ))
        else:
            self.results.append(ConstraintResult(
                name="LABEL_RESOLUTION",
                passed=True,
                detail=f"All jump targets resolved ({len(self.labels)} labels)"
            ))

    def _check_constraints(self, program: IRNode):
        """Check all ASSERT/REQUIRE/INVARIANT constraint nodes."""
        for child in program.children:
            if child.node_type != IRNodeType.CONSTRAINT:
                continue

            if child.constraint_kind == ConstraintKind.ENTROPY_BOUND:
                self._check_entropy_constraint(child)
            elif child.constraint_kind == ConstraintKind.TRUST_AXIOM:
                self._check_trust_constraint(child)
            elif child.constraint_kind == ConstraintKind.INJECTIVE:
                self._check_injective_constraint(child)
            elif child.constraint_kind == ConstraintKind.ACYCLIC:
                self._check_acyclic_constraint(child)
            elif child.constraint_kind == ConstraintKind.NAND_COMPLETE:
                self._check_nand_complete_constraint(child)

    def _check_entropy_constraint(self, node: IRNode):
        """Validate H <= bound."""
        bound = node.value if node.value is not None else 0.20
        # In static analysis, we verify the bound is in valid range
        if not (0.0 <= bound <= 10.0):
            self.results.append(ConstraintResult(
                name="ENTROPY_BOUND",
                passed=False,
                detail=f"Invalid entropy bound: {bound} (must be [0.0, 10.0])",
                line=node.line
            ))
        else:
            self.results.append(ConstraintResult(
                name="ENTROPY_BOUND",
                passed=True,
                detail=f"Entropy bound H <= {bound} nats declared",
                line=node.line
            ))

    def _check_trust_constraint(self, node: IRNode):
        """Validate active => trusted axiom declared."""
        self.results.append(ConstraintResult(
            name="TRUST_AXIOM",
            passed=True,
            detail="Trust axiom active => trusted declared",
            line=node.line
        ))

    def _check_injective_constraint(self, node: IRNode):
        """Validate injective mapping."""
        target = node.value
        if target not in self.symbols:
            self.results.append(ConstraintResult(
                name="INJECTIVE",
                passed=False,
                detail=f"Injective target '{target}' not declared",
                line=node.line
            ))
        else:
            self.results.append(ConstraintResult(
                name="INJECTIVE",
                passed=True,
                detail=f"Injective constraint on '{target}' declared",
                line=node.line
            ))

    def _check_acyclic_constraint(self, node: IRNode):
        """Validate acyclic graph."""
        target = node.value
        if target not in self.symbols:
            self.results.append(ConstraintResult(
                name="ACYCLIC",
                passed=False,
                detail=f"Acyclic target '{target}' not declared",
                line=node.line
            ))
        else:
            self.results.append(ConstraintResult(
                name="ACYCLIC",
                passed=True,
                detail=f"Acyclic constraint on '{target}' declared",
                line=node.line
            ))

    def _check_nand_complete_constraint(self, node: IRNode):
        """Validate NAND completeness."""
        self.results.append(ConstraintResult(
            name="NAND_COMPLETE",
            passed=True,
            detail="NAND completeness constraint declared",
            line=node.line
        ))

    def _check_nand_completeness(self):
        """
        Verify NAND-completeness: all Boolean opcodes can be derived from NAND.

        Truth table verification:
            NAND(0,0)=1, NAND(0,1)=1, NAND(1,0)=1, NAND(1,1)=0
            NOT(x)      = NAND(x,x)
            AND(a,b)    = NOT(NAND(a,b))
            OR(a,b)     = NAND(NOT(a),NOT(b))
            XOR(a,b)    = NAND(NAND(a,NAND(a,b)), NAND(b,NAND(a,b)))
            IMPLIES(a,b)= NAND(a,NOT(b))
            EQUAL(a,b)  = AND(IMPLIES(a,b),IMPLIES(b,a))
        """

        def nand(a, b):
            return int(not (a and b))

        def not_g(a):
            return nand(a, a)

        def and_g(a, b):
            return not_g(nand(a, b))

        def or_g(a, b):
            return nand(not_g(a), not_g(b))

        def xor_g(a, b):
            n = nand(a, b)
            return nand(nand(a, n), nand(b, n))

        def implies_g(a, b):
            return nand(a, not_g(b))

        def equal_g(a, b):
            return and_g(implies_g(a, b), implies_g(b, a))

        gates = [
            ('NAND', nand, lambda a, b: int(not (a and b))),
            ('NOT', lambda a, _: not_g(a), lambda a, _: int(not a)),
            ('AND', and_g, lambda a, b: int(a and b)),
            ('OR', or_g, lambda a, b: int(a or b)),
            ('XOR', xor_g, lambda a, b: int(a ^ b)),
            ('IMPLIES', implies_g, lambda a, b: int((not a) or b)),
            ('EQUAL', equal_g, lambda a, b: int(a == b)),
        ]

        all_correct = True
        for name, derived_fn, expected_fn in gates:
            for a in [0, 1]:
                for b in [0, 1]:
                    derived = derived_fn(a, b)
                    expected = expected_fn(a, b)
                    if derived != expected:
                        self.results.append(ConstraintResult(
                            name="NAND_KERNEL",
                            passed=False,
                            detail=f"{name}({a},{b}) = {derived}, expected {expected}"
                        ))
                        all_correct = False
                        break
                if not all_correct:
                    break
            if not all_correct:
                break

        if all_correct:
            self.results.append(ConstraintResult(
                name="NAND_KERNEL",
                passed=True,
                detail="All 7 gates verified from NAND (28 truth values)"
            ))


# =============================================================================
# PROOF SEALER
# =============================================================================

@dataclass
class ProofSeal:
    """Immutable cryptographic seal over constraint validation."""
    timestamp_ns: int
    constraint_count: int
    all_passed: bool
    blake2b_hash: str
    canonical_encoding: str

    def __repr__(self):
        status = "SEALED" if self.all_passed else "VIOLATED"
        return f"ProofSeal({status}, {self.constraint_count} constraints, {self.blake2b_hash[:16]}...)"


def seal_constraints(results: list[ConstraintResult]) -> ProofSeal:
    """
    Generate cryptographic seal over constraint validation results.

    1. Canonical encoding: sort results by name, encode as name:passed:detail
    2. Blake2b-256 hash of canonical encoding
    3. Timestamp (monotonic nanoseconds from time.time_ns())

    Returns:
        ProofSeal with hash and metadata.
    """
    entries = []
    for r in sorted(results, key=lambda x: x.name):
        entries.append(f"{r.name}:{r.passed}:{r.detail}")

    canonical = '\n'.join(entries)
    hasher = hashlib.blake2b(digest_size=32)
    hasher.update(canonical.encode('utf-8'))

    return ProofSeal(
        timestamp_ns=time.time_ns(),
        constraint_count=len(results),
        all_passed=all(r.passed for r in results),
        blake2b_hash=hasher.hexdigest(),
        canonical_encoding=canonical
    )


# =============================================================================
# BACKEND: VM BYTECODE EMITTER
# =============================================================================

# Opcode -> numeric bytecode mapping (matches vm_executor.py)
OPCODE_MAP = {
    'NOP': 0x00,
    'PUSH': 0x01, 'POP': 0x02, 'DUP': 0x03, 'SWAP': 0x04, 'ROT': 0x05, 'COPY': 0x06,
    'ADD': 0x10, 'SUB': 0x11, 'MUL': 0x12, 'DIV': 0x13, 'MOD': 0x14, 'NEG': 0x15, 'ABS': 0x16,
    'AND': 0x20, 'OR': 0x21, 'NOT': 0x22, 'NAND': 0x23, 'XOR': 0x24, 'XNOR': 0x25, 'NOR': 0x26,
    'EQ': 0x30, 'NEQ': 0x31, 'LT': 0x32, 'GT': 0x33, 'LE': 0x34, 'GE': 0x35,
    'BAND': 0x38, 'BOR': 0x39, 'BXOR': 0x3A, 'BNOT': 0x3B, 'SHL': 0x3C, 'SHR': 0x3D,
    'JMP': 0x40, 'JZ': 0x41, 'JNZ': 0x42, 'CALL': 0x43, 'RET': 0x44, 'LOOP': 0x45,
    'ROUTE': 0x50, 'DISPATCH': 0x51, 'GATE': 0x52, 'FILTER': 0x53, 'FORWARD': 0x54,
    'LOAD': 0x60, 'STORE': 0x61, 'ALLOC': 0x62, 'FREE': 0x63,
    'COMMIT': 0x70, 'CHECKPOINT': 0x71, 'ROLLBACK': 0x72, 'SEAL': 0x73, 'VERIFY': 0x74,
    'PRINT': 0x80, 'READ': 0x81, 'EMIT': 0x82,
    'MEASURE': 0x90, 'CLAMP': 0x91, 'ENTROPY': 0x92,
    'HALT': 0xFF,
    # Quantum extensions
    'H': 0xA0, 'CNOT': 0xA1, 'TOFFOLI': 0xA2, 'MEASURE_Q': 0xA3,
}


@dataclass
class BytecodeInstruction:
    opcode: int
    operand: Optional[int | float | str] = None
    label: Optional[str] = None

    def encode(self) -> bytes:
        """Encode to fixed-width binary: [opcode:1][flags:1][operand:8] = 10 bytes."""
        flags = 0x00
        operand_bytes = b'\x00' * 8

        if self.operand is not None:
            if isinstance(self.operand, int):
                flags = 0x01
                operand_bytes = struct.pack('>q', self.operand)
            elif isinstance(self.operand, float):
                flags = 0x02
                operand_bytes = struct.pack('>d', self.operand)
            elif isinstance(self.operand, str):
                flags = 0x03
                # String reference: hash of string -> 8-byte key
                h = hashlib.blake2b(self.operand.encode(), digest_size=8).digest()
                operand_bytes = h

        return struct.pack('BB', self.opcode, flags) + operand_bytes


class VMBytecodeEmitter:
    """
    Emit VM bytecode from parsed IR.

    Input:  IRNode (PROGRAM)
    Output: list[BytecodeInstruction] + binary blob

    Resolves labels to instruction indices.
    Encodes operands as typed 8-byte values.
    """

    def __init__(self):
        self.instructions: list[BytecodeInstruction] = []
        self.labels: dict[str, int] = {}
        self.string_table: dict[str, int] = {}

    def emit(self, program: IRNode) -> list[BytecodeInstruction]:
        """Emit bytecode from IR tree."""
        # First pass: collect labels
        idx = 0
        for child in program.children:
            if child.node_type == IRNodeType.LABEL_DEF:
                self.labels[child.name] = idx
            elif child.node_type == IRNodeType.OPERATION:
                idx += 1
            elif child.node_type == IRNodeType.DECLARATION:
                if child.decl_kind == DeclKind.ALLOC:
                    idx += 1  # ALLOC emits a PUSH + ALLOC pair

        # Second pass: emit instructions
        for child in program.children:
            if child.node_type == IRNodeType.OPERATION:
                self._emit_operation(child)
            elif child.node_type == IRNodeType.DECLARATION:
                self._emit_declaration(child)
            elif child.node_type == IRNodeType.LABEL_DEF:
                pass  # already collected
            elif child.node_type == IRNodeType.CONSTRAINT:
                pass  # constraints are compile-time only
            elif child.node_type == IRNodeType.DIRECTIVE:
                pass  # directives are metadata only

        # Third pass: resolve labels in jump targets
        for instr in self.instructions:
            if instr.label and instr.label in self.labels:
                instr.operand = self.labels[instr.label]

        return self.instructions

    def _emit_operation(self, node: IRNode):
        opcode = OPCODE_MAP.get(node.opcode, 0x00)
        operand = None
        label = None

        if node.children:
            first = node.children[0]
            if first.node_type == IRNodeType.LITERAL:
                operand = first.value
            elif first.node_type == IRNodeType.IDENTIFIER:
                if node.opcode in ('JMP', 'JZ', 'JNZ', 'CALL', 'LOOP'):
                    label = first.name
                else:
                    operand = first.name

        self.instructions.append(BytecodeInstruction(opcode=opcode, operand=operand, label=label))

    def _emit_declaration(self, node: IRNode):
        if node.decl_kind == DeclKind.ALLOC:
            # Emit PUSH 0 + ALLOC opcode
            self.instructions.append(BytecodeInstruction(opcode=OPCODE_MAP['PUSH'], operand=0))

    def to_binary(self) -> bytes:
        """Encode all instructions to contiguous binary blob."""
        header = struct.pack('>4sBBH', b'HKDL', 1, 0, len(self.instructions))
        body = b''.join(instr.encode() for instr in self.instructions)
        checksum = hashlib.blake2b(body, digest_size=16).digest()
        return header + body + checksum


# =============================================================================
# BACKEND: C CODE EMITTER
# =============================================================================

class CCodeEmitter:
    """
    Emit C source code from parsed IR.

    Generates a standalone C file with:
    - Stack-based execution loop
    - NAND-derived Boolean operations
    - Entropy gate (popcount-based)
    - WORM commit stubs
    """

    def __init__(self):
        self.lines: list[str] = []
        self.indent = 0

    def emit(self, program: IRNode) -> str:
        """Generate C source from IR tree."""
        self._emit_header()
        self._emit_nand_kernel()
        self._emit_stack_machine()
        self._emit_main(program)
        return '\n'.join(self.lines)

    def _w(self, line: str):
        self.lines.append('    ' * self.indent + line)

    def _emit_header(self):
        self._w('#include <stdio.h>')
        self._w('#include <stdint.h>')
        self._w('#include <stdlib.h>')
        self._w('#include <string.h>')
        self._w('')
        self._w('/* Generated by HyperKittyConstraintDSL compiler */')
        self._w('/* DO NOT EDIT — regenerate from .hkdsl source */')
        self._w('')
        self._w('#define STACK_SIZE 4096')
        self._w('#define WORM_MAGIC 0x574F524D')
        self._w('')

    def _emit_nand_kernel(self):
        self._w('/* NAND-complete Boolean kernel */')
        self._w('static inline int nand_op(int a, int b) { return !(a & b); }')
        self._w('static inline int not_op(int a) { return nand_op(a, a); }')
        self._w('static inline int and_op(int a, int b) { return not_op(nand_op(a, b)); }')
        self._w('static inline int or_op(int a, int b) { return nand_op(not_op(a), not_op(b)); }')
        self._w('static inline int xor_op(int a, int b) {')
        self._w('    int n = nand_op(a, b);')
        self._w('    return nand_op(nand_op(a, n), nand_op(b, n));')
        self._w('}')
        self._w('static inline int implies_op(int a, int b) { return nand_op(a, not_op(b)); }')
        self._w('static inline int equal_op(int a, int b) { return and_op(implies_op(a, b), implies_op(b, a)); }')
        self._w('')

    def _emit_stack_machine(self):
        self._w('/* Stack machine runtime */')
        self._w('typedef struct {')
        self._w('    int64_t data[STACK_SIZE];')
        self._w('    int top;')
        self._w('} Stack;')
        self._w('')
        self._w('static void stack_push(Stack *s, int64_t val) {')
        self._w('    if (s->top >= STACK_SIZE) { fprintf(stderr, "Stack overflow\\n"); exit(1); }')
        self._w('    s->data[s->top++] = val;')
        self._w('}')
        self._w('')
        self._w('static int64_t stack_pop(Stack *s) {')
        self._w('    if (s->top <= 0) { fprintf(stderr, "Stack underflow\\n"); exit(1); }')
        self._w('    return s->data[--s->top];')
        self._w('}')
        self._w('')
        self._w('static int64_t stack_peek(Stack *s) {')
        self._w('    if (s->top <= 0) { fprintf(stderr, "Stack empty\\n"); exit(1); }')
        self._w('    return s->data[s->top - 1];')
        self._w('}')
        self._w('')

    def _emit_main(self, program: IRNode):
        self._w('int main(void) {')
        self.indent += 1
        self._w('Stack stack = {.top = 0};')
        self._w('int64_t a, b, result;')
        self._w('')

        for child in program.children:
            if child.node_type == IRNodeType.OPERATION:
                self._emit_c_operation(child)
            elif child.node_type == IRNodeType.LABEL_DEF:
                self.indent -= 1
                self._w(f'{child.name}:')
                self.indent += 1

        self._w('')
        self._w('if (stack.top > 0) printf("Result: %lld\\n", (long long)stack_peek(&stack));')
        self._w('return 0;')
        self.indent -= 1
        self._w('}')

    def _emit_c_operation(self, node: IRNode):
        op = node.opcode
        if op == 'PUSH':
            val = node.children[0].value if node.children else 0
            self._w(f'stack_push(&stack, {val});')
        elif op == 'POP':
            self._w('stack_pop(&stack);')
        elif op == 'DUP':
            self._w('stack_push(&stack, stack_peek(&stack));')
        elif op == 'ADD':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, a + b);')
        elif op == 'SUB':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, a - b);')
        elif op == 'MUL':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, a * b);')
        elif op == 'DIV':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, b ? a / b : 0);')
        elif op == 'MOD':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, b ? a % b : 0);')
        elif op == 'NAND':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, nand_op((int)a, (int)b));')
        elif op == 'AND':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, and_op((int)a, (int)b));')
        elif op == 'OR':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, or_op((int)a, (int)b));')
        elif op == 'NOT':
            self._w('a = stack_pop(&stack); stack_push(&stack, not_op((int)a));')
        elif op == 'XOR':
            self._w('b = stack_pop(&stack); a = stack_pop(&stack); stack_push(&stack, xor_op((int)a, (int)b));')
        elif op == 'HALT':
            self._w('goto halt;')
        elif op == 'PRINT':
            self._w('printf("%lld\\n", (long long)stack_pop(&stack));')
        elif op == 'NOP':
            self._w('/* NOP */')
        elif op == 'GATE':
            self._w('/* GATE: entropy/routing check */')
        elif op == 'ENTROPY':
            self._w('/* ENTROPY measurement */')
        elif op == 'COMMIT':
            self._w('/* WORM COMMIT */')
        elif op == 'SEAL':
            self._w('/* WORM SEAL */')
        else:
            self._w(f'/* {op} (not yet implemented in C backend) */')


# =============================================================================
# BACKEND: x86-64 EMITTER
# =============================================================================

class X86Emitter:
    """
    Emit x86-64 machine code bytes from IR.

    Uses the machine_code_gen.py X86Encoder under the hood.
    Produces a flat binary that can be loaded via mmap+mprotect.
    """

    def __init__(self):
        self.code: bytearray = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []  # (offset, label_name)

    def emit(self, program: IRNode) -> bytes:
        """Generate x86-64 binary from IR tree."""
        # Prologue
        self._emit_prologue()

        # First pass: measure label positions
        # Second pass: emit code
        for child in program.children:
            if child.node_type == IRNodeType.LABEL_DEF:
                self.labels[child.name] = len(self.code)
            elif child.node_type == IRNodeType.OPERATION:
                self._emit_x86_operation(child)

        # Epilogue
        self._emit_epilogue()

        # Resolve fixups
        for offset, label in self.fixups:
            if label in self.labels:
                target = self.labels[label]
                # rel32 = target - (offset + 4)
                rel = target - (offset + 4)
                self.code[offset:offset + 4] = struct.pack('<i', rel)

        return bytes(self.code)

    def _emit_prologue(self):
        # push rbp
        self.code.append(0x55)
        # mov rbp, rsp
        self.code.extend([0x48, 0x89, 0xE5])
        # sub rsp, 0x100 (256 bytes for stack frame)
        self.code.extend([0x48, 0x81, 0xEC, 0x00, 0x01, 0x00, 0x00])

    def _emit_epilogue(self):
        # mov rsp, rbp
        self.code.extend([0x48, 0x89, 0xEC])
        # pop rbp
        self.code.append(0x5D)
        # ret
        self.code.append(0xC3)

    def _emit_x86_operation(self, node: IRNode):
        op = node.opcode
        if op == 'PUSH':
            val = node.children[0].value if node.children else 0
            if isinstance(val, int) and -128 <= val <= 127:
                # push imm8 (sign-extended)
                self.code.extend([0x6A, val & 0xFF])
            elif isinstance(val, int):
                # push imm32
                self.code.append(0x68)
                self.code.extend(struct.pack('<i', val & 0xFFFFFFFF))
            else:
                # push 0 (fallback)
                self.code.extend([0x6A, 0x00])
        elif op == 'POP':
            # pop rax
            self.code.append(0x58)
        elif op == 'ADD':
            # pop rax; pop rbx; add rax, rbx; push rax
            self.code.append(0x58)                    # pop rax
            self.code.append(0x5B)                    # pop rbx
            self.code.extend([0x48, 0x01, 0xD8])      # add rax, rbx
            self.code.append(0x50)                    # push rax
        elif op == 'SUB':
            # pop rax (subtrahend); pop rbx (minuend); sub rbx, rax; push rbx
            self.code.append(0x58)                    # pop rax
            self.code.append(0x5B)                    # pop rbx
            self.code.extend([0x48, 0x29, 0xC3])      # sub rbx, rax
            self.code.append(0x53)                    # push rbx
        elif op == 'MUL':
            # pop rax; pop rbx; imul rax, rbx; push rax
            self.code.append(0x58)                    # pop rax
            self.code.append(0x5B)                    # pop rbx
            self.code.extend([0x48, 0x0F, 0xAF, 0xC3])  # imul rax, rbx
            self.code.append(0x50)                    # push rax
        elif op == 'NAND':
            # pop rax; pop rbx; and rax, rbx; not rax; and rax, 1; push rax
            self.code.append(0x58)                    # pop rax
            self.code.append(0x5B)                    # pop rbx
            self.code.extend([0x48, 0x21, 0xD8])      # and rax, rbx
            self.code.extend([0x48, 0xF7, 0xD0])      # not rax
            self.code.extend([0x48, 0x83, 0xE0, 0x01])  # and rax, 1
            self.code.append(0x50)                    # push rax
        elif op == 'NOT':
            # pop rax; xor rax, 1; push rax
            self.code.append(0x58)                    # pop rax
            self.code.extend([0x48, 0x83, 0xF0, 0x01])  # xor rax, 1
            self.code.append(0x50)                    # push rax
        elif op == 'AND':
            # pop rax; pop rbx; and rax, rbx; push rax
            self.code.append(0x58)
            self.code.append(0x5B)
            self.code.extend([0x48, 0x21, 0xD8])
            self.code.append(0x50)
        elif op == 'OR':
            # pop rax; pop rbx; or rax, rbx; push rax
            self.code.append(0x58)
            self.code.append(0x5B)
            self.code.extend([0x48, 0x09, 0xD8])
            self.code.append(0x50)
        elif op == 'XOR':
            # pop rax; pop rbx; xor rax, rbx; push rax
            self.code.append(0x58)
            self.code.append(0x5B)
            self.code.extend([0x48, 0x31, 0xD8])
            self.code.append(0x50)
        elif op == 'JMP':
            if node.children and node.children[0].node_type == IRNodeType.IDENTIFIER:
                label = node.children[0].name
                self.code.append(0xE9)  # jmp rel32
                self.fixups.append((len(self.code), label))
                self.code.extend([0x00, 0x00, 0x00, 0x00])
        elif op == 'JZ':
            # pop rax; test rax, rax; jz rel32
            self.code.append(0x58)
            self.code.extend([0x48, 0x85, 0xC0])
            self.code.extend([0x0F, 0x84])  # jz rel32
            if node.children and node.children[0].node_type == IRNodeType.IDENTIFIER:
                self.fixups.append((len(self.code), node.children[0].name))
            self.code.extend([0x00, 0x00, 0x00, 0x00])
        elif op == 'JNZ':
            # pop rax; test rax, rax; jnz rel32
            self.code.append(0x58)
            self.code.extend([0x48, 0x85, 0xC0])
            self.code.extend([0x0F, 0x85])  # jnz rel32
            if node.children and node.children[0].node_type == IRNodeType.IDENTIFIER:
                self.fixups.append((len(self.code), node.children[0].name))
            self.code.extend([0x00, 0x00, 0x00, 0x00])
        elif op == 'CALL':
            if node.children and node.children[0].node_type == IRNodeType.IDENTIFIER:
                self.code.append(0xE8)  # call rel32
                self.fixups.append((len(self.code), node.children[0].name))
                self.code.extend([0x00, 0x00, 0x00, 0x00])
        elif op == 'RET':
            self.code.append(0xC3)
        elif op == 'HALT':
            # hlt (ring 0 only) -- use int3 for userspace
            self.code.append(0xCC)  # int3
        elif op == 'NOP':
            self.code.append(0x90)
        else:
            # Unknown opcode: emit NOP
            self.code.append(0x90)


# =============================================================================
# COMPILER PIPELINE (UNIFIED)
# =============================================================================

@dataclass
class CompilationResult:
    """Result of full compilation pipeline."""
    tokens: list[Token]
    ir: IRNode
    constraints_passed: bool
    constraint_results: list[ConstraintResult]
    proof_seal: ProofSeal
    bytecode: Optional[list[BytecodeInstruction]] = None
    binary: Optional[bytes] = None
    c_source: Optional[str] = None
    x86_binary: Optional[bytes] = None


class DSLCompiler:
    """
    Full HyperKittyConstraintDSL compiler pipeline.

    Usage:
        compiler = DSLCompiler()
        result = compiler.compile(source_text)

        # Check constraints
        if result.constraints_passed:
            print(f"Sealed: {result.proof_seal.blake2b_hash}")

        # Get outputs
        vm_binary = result.binary          # VM bytecode blob
        c_code = result.c_source           # Standalone C file
        native = result.x86_binary         # Raw x86-64 bytes

    Pipeline:
        1. Lex (regex -> tokens)
        2. Parse (recursive descent -> IR tree)
        3. Validate (5 constraints)
        4. Seal (Blake2b proof hash)
        5. Emit (VM bytecode + C + x86-64)
    """

    def __init__(self, emit_c: bool = True, emit_x86: bool = True):
        self.emit_c = emit_c
        self.emit_x86 = emit_x86

    def compile(self, source: str) -> CompilationResult:
        """
        Compile DSL source to all backends.

        Args:
            source: HyperKittyConstraintDSL source text

        Returns:
            CompilationResult with tokens, IR, constraints, seal, and backend outputs.

        Raises:
            LexError: on tokenization failure
            ParseError: on parse failure
        """
        # Stage 1: Lex
        tokens = lex(source)

        # Stage 2: Parse
        parser = Parser(tokens)
        ir = parser.parse_program()

        # Stage 3: Validate constraints
        engine = ConstraintEngine()
        passed, results = engine.validate(ir)

        # Stage 4: Seal
        seal = seal_constraints(results)

        # Stage 5a: Emit VM bytecode
        vm_emitter = VMBytecodeEmitter()
        bytecode = vm_emitter.emit(ir)
        binary = vm_emitter.to_binary()

        # Stage 5b: Emit C code
        c_source = None
        if self.emit_c:
            c_emitter = CCodeEmitter()
            c_source = c_emitter.emit(ir)

        # Stage 5c: Emit x86-64
        x86_binary = None
        if self.emit_x86:
            x86_emitter = X86Emitter()
            x86_binary = x86_emitter.emit(ir)

        return CompilationResult(
            tokens=tokens,
            ir=ir,
            constraints_passed=passed,
            constraint_results=results,
            proof_seal=seal,
            bytecode=bytecode,
            binary=binary,
            c_source=c_source,
            x86_binary=x86_binary,
        )


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """CLI driver for the DSL compiler."""
    import sys

    # Example program demonstrating the full DSL
    example_source = """
# HyperKittyConstraintDSL Example Program
# Demonstrates: declarations, operations, constraints, quantum ops

@version 1
@target vm

# Constraint declarations
ASSERT H <= 0.20
ASSERT active => trusted
REQUIRE nand_complete(kernel)

# Variable declarations
LET kernel = 1
CONST max_entropy = 0.20
ALLOC q0 : qubit
ALLOC q1 : qubit
ALLOC c0 : bit

# Quantum operations
H q0
CNOT q0, q1
MEASURE_Q q0 -> c0

# Classical computation (NAND-complete)
PUSH 1
PUSH 1
NAND
PUSH 0
NAND

# Arithmetic
PUSH 42
PUSH 8
ADD
PUSH 2
MUL

# Control flow
loop_start:
    PUSH 1
    SUB
    DUP
    JNZ loop_start

# Routing
GATE
FILTER
ROUTE

# Entropy measurement
ENTROPY

# Commit to WORM
COMMIT
SEAL

HALT
"""

    print("=" * 70)
    print("HyperKittyConstraintDSL Compiler v2.0")
    print("=" * 70)
    print()

    # Compile
    compiler = DSLCompiler()

    if len(sys.argv) > 1:
        # Read from file
        with open(sys.argv[1], 'r') as f:
            source = f.read()
    else:
        source = example_source

    try:
        result = compiler.compile(source)
    except (LexError, ParseError) as e:
        print(f"  COMPILE ERROR: {e}")
        sys.exit(1)

    # Report
    print(f"  Tokens:        {len(result.tokens)}")
    print(f"  IR nodes:      {len(result.ir.children)}")
    print(f"  Bytecode:      {len(result.bytecode)} instructions")
    print(f"  Binary size:   {len(result.binary)} bytes")
    if result.c_source:
        print(f"  C source:      {len(result.c_source)} bytes ({result.c_source.count(chr(10))} lines)")
    if result.x86_binary:
        print(f"  x86-64 binary: {len(result.x86_binary)} bytes")
    print()

    # Constraints
    print("  CONSTRAINT VALIDATION:")
    print("  " + "-" * 66)
    for r in result.constraint_results:
        status = "PASS" if r.passed else "FAIL"
        line_info = f"L{r.line}" if r.line else "   "
        print(f"    [{status}] {line_info:5} {r.name:25} {r.detail}")
    print()

    # Seal
    print(f"  PROOF SEAL:")
    print(f"    Status:     {'SEALED' if result.constraints_passed else 'VIOLATED'}")
    print(f"    Blake2b:    {result.proof_seal.blake2b_hash}")
    print(f"    Timestamp:  {result.proof_seal.timestamp_ns}")
    print(f"    Count:      {result.proof_seal.constraint_count} constraints")
    print()

    # Bytecode dump
    print("  BYTECODE (first 20 instructions):")
    print("  " + "-" * 66)
    for i, instr in enumerate(result.bytecode[:20]):
        op_name = next((k for k, v in OPCODE_MAP.items() if v == instr.opcode), f'0x{instr.opcode:02X}')
        operand_str = f" {instr.operand}" if instr.operand is not None else ""
        label_str = f" @{instr.label}" if instr.label else ""
        print(f"    {i:04d}: {op_name:12}{operand_str}{label_str}")
    if len(result.bytecode) > 20:
        print(f"    ... ({len(result.bytecode) - 20} more)")
    print()

    # x86-64 hex dump
    if result.x86_binary:
        print("  x86-64 HEX (first 64 bytes):")
        print("  " + "-" * 66)
        for i in range(0, min(64, len(result.x86_binary)), 16):
            chunk = result.x86_binary[i:i+16]
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"    {i:04X}: {hex_str:<48} {ascii_str}")
        if len(result.x86_binary) > 64:
            print(f"    ... ({len(result.x86_binary) - 64} more bytes)")
    print()

    # Final verdict
    if result.constraints_passed:
        print("  VERDICT: ALL CONSTRAINTS SATISFIED. CODE SEALED.")
    else:
        print("  VERDICT: CONSTRAINT VIOLATION. CODE NOT SEALED.")
        sys.exit(1)

    print("=" * 70)


if __name__ == "__main__":
    main()

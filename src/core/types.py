"""
Layer 1: Primitive Types & Bounded Values
Part of SOVEREIGN PYTHON LLM ENGINE

Type-safe primitives with validation and bounds checking.
All types are immutable and enforce invariants at construction.
"""

from typing import NewType, TypeVar, Generic
from pydantic import BaseModel, Field, validator, model_validator
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone


# ==========================================
# Identifier Types
# ==========================================

TaskID = NewType('TaskID', str)
ModelID = NewType('ModelID', str)
ToolID = NewType('ToolID', str)
AgentID = NewType('AgentID', str)
ExpertID = NewType('ExpertID', int)  # 0-999 for 1000 experts


# ==========================================
# Bounded Integer Types
# ==========================================

class PositiveInt(BaseModel):
    """Integer > 0"""
    value: int = Field(gt=0)

    def __int__(self) -> int:
        return self.value

    def __repr__(self) -> str:
        return f"PositiveInt({self.value})"


class NonNegativeInt(BaseModel):
    """Integer >= 0"""
    value: int = Field(ge=0)

    def __int__(self) -> int:
        return self.value


class BoundedInt(BaseModel):
    """Integer with custom bounds [min_val, max_val]"""
    value: int
    min_val: int
    max_val: int

    @model_validator(mode='after')
    def check_bounds(self):
        if not (self.min_val <= self.value <= self.max_val):
            raise ValueError(f"Value {self.value} outside bounds [{self.min_val}, {self.max_val}]")
        return self

    def __int__(self) -> int:
        return self.value


class ExpertIndex(BaseModel):
    """Expert index in range [0, 999] for 1000-expert MoE"""
    value: int = Field(ge=0, lt=1000)

    def __int__(self) -> int:
        return self.value

    @classmethod
    def from_int(cls, i: int) -> 'ExpertIndex':
        """Convenience constructor"""
        return cls(value=i)


# ==========================================
# Bounded Float Types
# ==========================================

class Probability(BaseModel):
    """Float in [0.0, 1.0]"""
    value: float = Field(ge=0.0, le=1.0)

    def __float__(self) -> float:
        return self.value


class Temperature(BaseModel):
    """
    LLM sampling temperature in [0.0, 2.0].

    Values:
    - 0.0: deterministic (argmax)
    - 1.0: standard sampling
    - 2.0: maximum creativity
    """
    value: float = Field(ge=0.0, le=2.0)

    def __float__(self) -> float:
        return self.value

    @classmethod
    def deterministic(cls) -> 'Temperature':
        return cls(value=0.0)

    @classmethod
    def standard(cls) -> 'Temperature':
        return cls(value=1.0)


class JordanEigenvalue(BaseModel):
    """
    Eigenvalue for Jordan block in quantum MoE.

    Constrained to unit circle: |λ| <= 1.0 for numerical stability.
    """
    value: float = Field(ge=-1.0, le=1.0)

    def __float__(self) -> float:
        return self.value


# ==========================================
# Exact Decimal (Financial/Critical)
# ==========================================

class ExactDecimal(BaseModel):
    """
    Exact decimal representation (no float precision loss).

    Use for financial calculations or critical accuracy requirements.
    """
    value: Decimal

    @validator('value')
    def finite_check(cls, v):
        if not v.is_finite():
            raise ValueError(f"Decimal must be finite, got {v}")
        return v

    def __repr__(self) -> str:
        return f"ExactDecimal('{self.value}')"

    @classmethod
    def from_string(cls, s: str) -> 'ExactDecimal':
        """Parse from string to avoid float conversion"""
        return cls(value=Decimal(s))


# ==========================================
# Validated Paths
# ==========================================

class ValidatedPath(BaseModel):
    """
    Path that must exist on filesystem.

    Validates at construction time.
    """
    path: Path

    @validator('path')
    def path_exists(cls, v):
        if not v.exists():
            raise ValueError(f"Path does not exist: {v}")
        return v

    def __repr__(self) -> str:
        return f"ValidatedPath({self.path})"

    def __str__(self) -> str:
        return str(self.path)


class ValidatedDirectory(BaseModel):
    """Directory that must exist and be a directory."""
    path: Path

    @validator('path')
    def is_directory(cls, v):
        if not v.exists():
            raise ValueError(f"Directory does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Path is not a directory: {v}")
        return v


class ValidatedFile(BaseModel):
    """File that must exist and be a file."""
    path: Path

    @validator('path')
    def is_file(cls, v):
        if not v.exists():
            raise ValueError(f"File does not exist: {v}")
        if not v.is_file():
            raise ValueError(f"Path is not a file: {v}")
        return v


# ==========================================
# Timestamp Types
# ==========================================

class UTCTimestamp(BaseModel):
    """
    UTC timestamp (timezone-aware).

    Always normalized to UTC.
    """
    value: datetime

    @validator('value')
    def ensure_utc(cls, v):
        if v.tzinfo is None:
            # Assume UTC if naive
            return v.replace(tzinfo=timezone.utc)
        # Convert to UTC
        return v.astimezone(timezone.utc)

    @classmethod
    def now(cls) -> 'UTCTimestamp':
        """Get current UTC timestamp"""
        return cls(value=datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"UTCTimestamp({self.value.isoformat()})"


# ==========================================
# Bounded Collections
# ==========================================

T = TypeVar('T')


class NonEmptyList(BaseModel, Generic[T]):
    """List with at least one element"""
    items: list[T] = Field(min_items=1)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> T:
        return self.items[idx]


class BoundedList(BaseModel, Generic[T]):
    """List with size bounds [min_size, max_size]"""
    items: list[T]
    min_size: int
    max_size: int

    @model_validator(mode='after')
    def check_size(self):
        if not (self.min_size <= len(self.items) <= self.max_size):
            raise ValueError(
                f"List size {len(self.items)} outside bounds [{self.min_size}, {self.max_size}]"
            )
        return self


# ==========================================
# Validated Strings
# ==========================================

class NonEmptyString(BaseModel):
    """String that cannot be empty or whitespace-only"""
    value: str = Field(min_length=1)

    @validator('value')
    def no_whitespace_only(cls, v):
        if not v.strip():
            raise ValueError("String cannot be whitespace-only")
        return v

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"NonEmptyString('{self.value}')"


class BoundedString(BaseModel):
    """String with length bounds"""
    value: str
    min_length: int = 0
    max_length: int = 1000

    @model_validator(mode='after')
    def check_length(self):
        if not (self.min_length <= len(self.value) <= self.max_length):
            raise ValueError(
                f"String length {len(self.value)} outside bounds [{self.min_length}, {self.max_length}]"
            )
        return self


# ==========================================
# Token Representation
# ==========================================

class TokenID(BaseModel):
    """
    Token identifier with binary representation.

    Supports quantum encoding via binary_repr.
    """
    value: int = Field(ge=0)
    binary_repr: str | None = None

    @model_validator(mode='after')
    def compute_binary(self):
        if self.binary_repr is None:
            # Compute 16-bit binary representation
            self.binary_repr = bin(self.value)[2:].zfill(16)
        return self

    def __int__(self) -> int:
        return self.value

    def get_binary(self) -> str:
        """Get binary representation for quantum encoding"""
        return self.binary_repr or bin(self.value)[2:].zfill(16)


# ==========================================
# Model Context Window
# ==========================================

class ContextWindow(BaseModel):
    """
    Model context window size.

    Common values: 2048, 4096, 8192, 32768, 128000
    """
    size: int = Field(gt=0)
    unit: str = "tokens"

    @validator('size')
    def power_of_two(cls, v):
        """Context windows are typically powers of 2"""
        if v & (v - 1) != 0:
            # Not a power of 2, but we allow it (warn only)
            pass
        return v

    def __int__(self) -> int:
        return self.size


# ==========================================
# Expert Activation Sparsity
# ==========================================

class SparsityRatio(BaseModel):
    """
    MoE sparsity ratio (activated / total experts).

    For quantum MoE: 25/1000 = 0.025 (2.5%)
    """
    activated: int = Field(gt=0)
    total: int = Field(gt=0)

    @model_validator(mode='after')
    def validate_ratio(self):
        if self.activated > self.total:
            raise ValueError(
                f"Activated experts ({self.activated}) cannot exceed total ({self.total})"
            )
        return self

    def as_float(self) -> float:
        """Get sparsity as float in [0, 1]"""
        return self.activated / self.total

    def as_percentage(self) -> float:
        """Get sparsity as percentage"""
        return 100.0 * self.as_float()

    @classmethod
    def quantum_moe(cls) -> 'SparsityRatio':
        """Default sparsity for quantum MoE (25/1000)"""
        return cls(activated=25, total=1000)

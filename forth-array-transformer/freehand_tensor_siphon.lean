/-- Freehand Tensor Siphon
    Derives tensor contractions from matrix multiplication and exposes
    structural invariants suitable for Lean verification.
-/

namespace FreehandTensor

universe u v w

/-- A finite index space. -/
structure Index where
  card : Nat

/-- A tensor over finite index spaces.  The payload is intentionally abstract:
    the structural layer reasons about shapes and contractions first. -/
structure Tensor (α : Type u) where
  shape : List Nat
  data  : α

/-- Matrix shape. -/
structure MatrixShape where
  rows : Nat
  cols : Nat

/-- Matrix multiplication compatibility. -/
def Compatible (a b : MatrixShape) : Prop := a.cols = b.rows

/-- Result shape of compatible matrix multiplication. -/
def MatmulShape (a b : MatrixShape) (h : Compatible a b) : MatrixShape :=
  { rows := a.rows, cols := b.cols }

/-- The contraction index is the shared matrix dimension. -/
def SiphonIndex (a b : MatrixShape) (h : Compatible a b) : Nat := a.cols

/-- A freehand tensor contraction schema induced by matrix multiplication.
    The shared index is consumed; outer indices survive. -/
structure Siphon (a b : MatrixShape) (h : Compatible a b) where
  leftIndex  : Nat := a.rows
  contracted : Nat := SiphonIndex a b h
  rightIndex : Nat := b.cols

/-- Shape equation induced by a matrix product. -/
theorem siphon_shape (a b : MatrixShape) (h : Compatible a b) :
    (MatmulShape a b h).rows = a.rows ∧
    (MatmulShape a b h).cols = b.cols := by
  constructor <;> rfl

/-- The contraction dimension is exactly the shared inner dimension. -/
theorem siphon_contracts_inner_dimension
    (a b : MatrixShape) (h : Compatible a b) :
    SiphonIndex a b h = a.cols := by
  rfl

/-- Compatibility transports the right matrix row dimension to the siphon. -/
theorem siphon_right_dimension
    (a b : MatrixShape) (h : Compatible a b) :
    SiphonIndex a b h = b.rows := by
  exact h.symm

/-- A tensor contraction can be represented as a matrix multiplication when
    its free indices are partitioned into a left and right boundary and one
    internal index is contracted. -/
structure Contraction where
  left : Nat
  contracted : Nat
  right : Nat

/-- The canonical contraction extracted from compatible matrix shapes. -/
def fromMatmul (a b : MatrixShape) (h : Compatible a b) : Contraction :=
  { left := a.rows, contracted := a.cols, right := b.cols }

/-- The matrix product is the contraction over the shared index.
    This theorem captures the structural, rather than numerical, identity. -/
theorem matmul_is_siphon
    (a b : MatrixShape) (h : Compatible a b) :
    (fromMatmul a b h).left = a.rows ∧
    (fromMatmul a b h).contracted = a.cols ∧
    (fromMatmul a b h).right = b.cols := by
  simp [fromMatmul]

/-- Composition of siphons: consecutive matrix products compose their
    contracted structure. -/
def compose (x y : Contraction) (compatible : x.right = y.left) : Contraction :=
  { left := x.left
    contracted := x.contracted
    right := y.right }

/-- Composition preserves the outer boundaries. -/
theorem compose_outer
    (x y : Contraction) (h : x.right = y.left) :
    (compose x y h).left = x.left ∧
    (compose x y h).right = y.right := by
  constructor <;> rfl

/-- A freehand tensor expression records the surviving free indices and
    contracted indices. -/
structure FreehandTensor where
  freeLeft : Nat
  contracted : List Nat
  freeRight : Nat

/-- Convert a matrix multiplication siphon to a freehand tensor. -/
def freehandOf (a b : MatrixShape) (h : Compatible a b) : FreehandTensor :=
  { freeLeft := a.rows
    contracted := [a.cols]
    freeRight := b.cols }

/-- Exactly one internal index is siphoned by ordinary matrix multiplication. -/
theorem ordinary_matmul_has_one_siphon
    (a b : MatrixShape) (h : Compatible a b) :
    (freehandOf a b h).contracted = [a.cols] := by
  rfl

/-- Siphon equivalence: two compatible matrix products induce the same
    freehand tensor schema when their three boundary dimensions agree. -/
def SameSiphon (x y : FreehandTensor) : Prop :=
  x.freeLeft = y.freeLeft ∧
  x.contracted = y.contracted ∧
  x.freeRight = y.freeRight

theorem same_siphon_refl (x : FreehandTensor) : SameSiphon x x := by
  simp [SameSiphon]

end FreehandTensor

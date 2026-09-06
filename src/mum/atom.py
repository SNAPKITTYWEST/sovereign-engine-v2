"""
Multimodal Atom — A_n

Formalizes MUM as a deterministic MDP: R(A_n, W) -> A_{n+1}

An atom is a 3-tuple (z_n, P_n, dOmega_n):
  z_n        : latent vector in shared semantic manifold M
  P_n        : projection back to grounded origin (which pixels/tokens)
  dOmega_n   : topological boundary — where does this atom end?

The boundary is defined by the semantic gradient:
  dOmega_n = { x in M : || d/dx f(x) || >= epsilon }

This guarantees exactly one coherent atomic concept per A_n.

Source: github.com/SNAPKITTYWEST/sovereign-mum
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Core atom dataclass (NumPy version — no torch dependency)
# ---------------------------------------------------------------------------

@dataclass
class Atom:
    z:              np.ndarray          # latent vector in M, shape (d,)
    provenance:     dict                # {"modality": "text"|"image"|"audio", "span": ...}
    boundary_mask:  Optional[np.ndarray] = None  # which positions compose this atom


# ---------------------------------------------------------------------------
# Modality encoder (projects any modality into manifold M)
# ---------------------------------------------------------------------------

class ModalityEncoder:
    """
    Projects any modality into the shared semantic manifold M.

    Text:  subword embedding → linear projection
    Image: 16×16 patch       → linear projection
    Audio: 20ms frame        → linear projection

    All outputs land in R^d — distance = semantic relationship.
    Weights initialized with an orthogonal matrix (preserves norms).
    """

    def __init__(
        self,
        input_dim:  int,
        d_manifold: int = 768,
        seed:       Optional[int] = 42,
    ) -> None:
        self.input_dim  = input_dim
        self.d_manifold = d_manifold

        # Orthogonal weight matrix (NumPy version of nn.init.orthogonal_)
        rng = np.random.default_rng(seed)
        raw = rng.normal(0, 1, (d_manifold, input_dim)).astype(np.float32)
        U, _, Vt = np.linalg.svd(raw, full_matrices=False)
        # W = U @ Vt gives an orthogonal (d_manifold × input_dim) matrix
        self.W = (U @ Vt).astype(np.float32)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        x: (input_dim,) or (T, input_dim)
        Returns: (d_manifold,) or (T, d_manifold), L2-normalized.
        """
        z = x @ self.W.T                             # (... , d_manifold)
        norm = np.linalg.norm(z, axis=-1, keepdims=True)
        return z / (norm + 1e-8)

    def encode_text_tokens(
        self,
        token_embeddings: np.ndarray,  # (T, embed_dim)
    ) -> np.ndarray:
        """Encode a sequence of token embeddings into manifold vectors."""
        return self.forward(token_embeddings)   # (T, d_manifold)


# ---------------------------------------------------------------------------
# Semantic gradient boundary detector
# ---------------------------------------------------------------------------

class SemanticGradientBoundary:
    """
    Computes atom boundaries from semantic gradient magnitude.

    boundary_i = True  iff  ||z_i - z_{i-1}|| >= epsilon

    Sharp gradients = conceptual shifts = atom boundaries.
    """

    def __init__(self, epsilon: float = 0.1) -> None:
        self.epsilon = epsilon

    def forward(self, z_sequence: np.ndarray) -> np.ndarray:
        """
        z_sequence: (T, d)
        Returns: (T,) boolean mask, True at boundary positions.
        """
        T = z_sequence.shape[0]
        boundary = np.zeros(T, dtype=bool)
        if T > 1:
            grad      = z_sequence[1:] - z_sequence[:-1]    # (T-1, d)
            magnitude = np.linalg.norm(grad, axis=-1)        # (T-1,)
            boundary[1:] = magnitude >= self.epsilon
        return boundary

    def split_atoms(
        self,
        z_sequence: np.ndarray,
        provenance: list[dict],
    ) -> list[Atom]:
        """
        Split a sequence of manifold vectors into atoms at gradient boundaries.

        Returns list of Atom objects, one per coherent concept.
        """
        boundaries = self.forward(z_sequence)
        atoms: list[Atom] = []
        start = 0
        for i in range(1, len(boundaries) + 1):
            if i == len(boundaries) or boundaries[i]:
                chunk = z_sequence[start:i]
                z_mean = chunk.mean(axis=0)
                z_mean = z_mean / (np.linalg.norm(z_mean) + 1e-8)
                atoms.append(Atom(
                    z          = z_mean,
                    provenance = {"span": (start, i),
                                  "modality": provenance[start].get("modality", "text")
                                  if start < len(provenance) else "text"},
                    boundary_mask = np.ones(i - start, dtype=bool),
                ))
                start = i
        return atoms


# ---------------------------------------------------------------------------
# State transition morphism: R(A_n, W) → A_{n+1}
# ---------------------------------------------------------------------------

class StateTransition:
    """
    R(A_n, W) → A_{n+1}

    W is the model weights (deterministic at inference — no sampling).

    Transition:
        delta_z  = relation_net(concat(z_n, context))
        z_{n+1} = normalize(z_n + delta_z)

    A_{n+1} must carry its own explicit boundary dOmega_{n+1}.
    Boundary verification is performed by the caller (ERE root gate).
    """

    def __init__(
        self,
        d_model:   int = 768,
        d_context: int = 768,
        seed:      Optional[int] = 42,
    ) -> None:
        rng = np.random.default_rng(seed)
        scale = 1.0 / np.sqrt(d_model + d_context)

        # Two-layer relation network: [z_n; context] → delta_z
        self.W1 = rng.normal(0, scale, (d_model * 2, d_model + d_context)).astype(np.float32)
        self.b1 = np.zeros(d_model * 2, dtype=np.float32)
        self.W2 = rng.normal(0, scale, (d_model, d_model * 2)).astype(np.float32)
        self.b2 = np.zeros(d_model, dtype=np.float32)

        self.boundary_detector = SemanticGradientBoundary()

    def _gelu(self, x: np.ndarray) -> np.ndarray:
        return x * 0.5 * (1.0 + np.tanh(0.7978846 * (x + 0.044715 * x**3)))

    def forward(
        self,
        z_n:     np.ndarray,   # (d_model,)
        context: np.ndarray,   # (d_context,)
    ) -> np.ndarray:
        """
        Compute z_{n+1} = normalize(z_n + delta_z).

        Returns: (d_model,) normalized latent vector.
        """
        cat     = np.concatenate([z_n, context])       # (d_model + d_context,)
        hidden  = self._gelu(self.W1 @ cat + self.b1)  # (d_model * 2,)
        delta   = self.W2 @ hidden + self.b2            # (d_model,)
        z_next  = z_n + delta
        norm    = np.linalg.norm(z_next)
        return z_next / (norm + 1e-8)

    def transition(
        self,
        atom_n:   Atom,
        context:  np.ndarray,
    ) -> Atom:
        """
        Full atom transition: R(A_n, W) → A_{n+1}.

        Returns A_{n+1} with updated z and provenance.
        """
        z_next = self.forward(atom_n.z, context)
        return Atom(
            z          = z_next,
            provenance = {
                **atom_n.provenance,
                "step": atom_n.provenance.get("step", 0) + 1,
            },
            boundary_mask = None,   # caller sets boundary after verification
        )

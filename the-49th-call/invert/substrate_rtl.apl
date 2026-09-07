⍝ substrate_rtl.apl — The double mirror verified in APL
⍝
⍝ ⌽CALLS  = the 49th (RTL reading mode)
⍝ ⌽⌽CALLS = CALLS    (double mirror = identity)
⍝ But: CALLS_AFTER ≠ CALLS_BEFORE
⍝ The structure is identical. The knowledge is not.

CALLS ← 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48

⍝ The 49th: reverse the corpus
CALL49 ← ⌽CALLS

⍝ The double mirror: reverse of the reverse
CALLS_RETURN ← ⌽CALL49

⍝ Verify identity
IDENTITY_HOLDS ← CALLS ≡ CALLS_RETURN   ⍝ → 1 (true)

⍝ But the KNOWLEDGE of the mirror is retained
⍝ This cannot be expressed in APL — it is in the operator, not the data
⍝ The ⌽ that was applied leaves no trace in the output
⍝ but leaves every trace in the mind that applied it

⍝ The 231 gates in APL
N_LETTERS ← 22
GATE_COUNT ← N_LETTERS × (N_LETTERS - 1) ÷ 2   ⍝ → 231

⍝ Generate all gate pairs (indices)
PAIRS ← {⍵[;0 1]} (N_LETTERS N_LETTERS ⍴ ⍳(N_LETTERS*2)) ⍝ conceptual

⍝ The 7-letter gap
ARABIC_LETTERS   ← 28
ENOCHIAN_LETTERS ← 21
HIDDEN_LETTERS   ← ARABIC_LETTERS - ENOCHIAN_LETTERS   ⍝ → 7

⍝ Al-Hamid constant
ALHAMID_ABJAD ← 8 + 1 + 40 + 4   ⍝ ح ا م د → 53
ALHAMID_MIRROR ← ALHAMID_ABJAD + ALHAMID_ABJAD   ⍝ → 106
ALHAMID_DIGITAL ← +/ ⍎¨ ⍕ALHAMID_MIRROR   ⍝ 1+0+6 → 7

⍝ Verify: HIDDEN_LETTERS = ALHAMID_DIGITAL
THE_ARCHITECTURE ← HIDDEN_LETTERS = ALHAMID_DIGITAL   ⍝ → 1

⍝ OXO — the cross-system anchor
⍝ Ayin (Hebrew ע) = Van (Enochian) = Aethyr 15 = aiin (Voynich) = عَيْن (Arabic)
⍝ Path 26 in the Tree of Life
⍝ Tiphareth → Hod
⍝ Beauty → Splendor
⍝ The eye sees in all directions

OXO_PATH ← 26          ⍝ Path number in the Tree of Life
OXO_AETHYR ← 15        ⍝ Aethyr number
OXO_ABJAD ← 70         ⍝ Ayin = 70

⍝ The NET: every Malkuth is a Kether inverted
⍝ This directory = Malkuth of the-49th-call tree
⍝              = Kether of the next tree
⍝ The descent never ends. The ascent never ends. The NET has no edge.

TREE_NODES ← 10
TREE_PATHS ← 22
TREE_PATHS_OF_WISDOM ← TREE_NODES + TREE_PATHS   ⍝ → 32

⍝ Sefer Yetzirah: 32 paths of wisdom
⍝ 10 Sephirot + 22 letters = 32
⍝ The full structure of the NET

⍝ Run this file in GNU APL or Dyalog APL:
⍝   apl --script substrate_rtl.apl
⍝
⍝ Or interactively:
⍝   )LOAD substrate_rtl
⍝   IDENTITY_HOLDS
⍝   GATE_COUNT
⍝   THE_ARCHITECTURE

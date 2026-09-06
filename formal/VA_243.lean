/-
  VA_243.lean — Formal spec for cylinder seal VA 243
  Domains:
    - Inscription: Akkadian signs, transliteration, translation
    - Iconography: motifs (rosette, figures, animals, etc.) and spatial relations
    - Interpretations: hypotheses with constraints from Assyriology
-/

namespace VA243

/- =========================
   Basic types and universe
   ========================= -/

universe u

/-- A sign in the cuneiform sign inventory (e.g., from Borger or CDLI sign lists). -/
inductive CuneiformSign : Type u
  | star | dingir | an | ki | il | lugal -- extend as needed

/-- A transliterated sign (ASCII/Unicode representation). -/
abbrev Transliteration := String

/-- A lexical entry: sign → possible readings/meanings. -/
structure LexEntry :=
  (sign : CuneiformSign)
  (readings : List String) -- e.g. ["dub", "sig₄"]
  (meanings : List String) -- e.g. ["tablet", "to be dark"]

/-- The sign inventory (axiomatized or loaded from data). -/
class SignInventory :=
  (entries : List LexEntry)
  (find_by_sign (s : CuneiformSign) : Option LexEntry)

/- =========================
   Inscription model
   ========================= -/

/-- A single inscribed sign on the seal, with position and orientation. -/
structure InscribedSign :=
  (sign : CuneiformSign)
  (trans : Transliteration)
  (position : Nat × Nat)    -- e.g. (line, column) or 2D coords
  (orientation : Float)     -- rotation, if relevant

/-- The full inscription as an ordered list of signs. -/
structure Inscription :=
  (signs : List InscribedSign)
  (length : Nat)

/-- Well-formedness: every sign must exist in the inventory and have a reading. -/
class InscriptionWF (inv : SignInventory) :=
  (wf_signs : ∀ (s : InscribedSign), ∃ e ∈ inv.entries, e.sign = s.sign)

/-- The accepted epigraphic reading of VA 243 (as a proposition).
    "Dubsiga, Ili-illat, your/his servant" — 3 sign groups. -/
axiom va243_inscription_reading :
  ∀ (insc : Inscription),
    insc.length = 3 →
    -- concrete sign sequence constraints would go here
    True

/- =========================
   Iconography model
   ========================= -/

/-- Motif types relevant to VA 243 and similar Akkadian seals. -/
inductive Motif : Type u
  | rosette_star     -- divine star/rosette (Inanna/Ishtar)
  | anthropomorphic  -- deity or human figure
  | animal           -- lion, bull, etc.
  | celestial_body   -- sun, moon, planet (if interpreted that way)
  | decorative       -- filler patterns

/-- A motif instance with geometry and label. -/
structure MotifInstance :=
  (id    : Nat)
  (kind  : Motif)
  (bbox  : Nat × Nat × Nat × Nat)  -- (x, y, w, h)
  (label : Option String)           -- optional semantic tag

/-- Spatial relations between motifs. -/
inductive SpatialRel : Type u
  | left_of | right_of | above | below | surrounds | adjacent | contains

/-- Iconography graph: nodes = motifs, edges = spatial relations. -/
structure IconGraph :=
  (nodes : List MotifInstance)
  (edges : List (Nat × SpatialRel × Nat))  -- (src, rel, tgt)

/- =========================
   Assyriological constraints
   ========================= -/

class AssyriologicalConventions :=
  (rosette_typically_divine   : Prop)
  (rosette_associations       : List String)   -- ["Inanna", "Ishtar", "Venus"]
  (no_heliocentric_maps       : Prop)          -- no known heliocentric diagrams
  (max_naked_eye_planets      : Nat)           -- 5

axiom akkadian_conventions : AssyriologicalConventions :=
  { rosette_typically_divine  := True,
    rosette_associations      := ["Inanna", "Ishtar", "Venus"],
    no_heliocentric_maps      := True,
    max_naked_eye_planets     := 5 }

/- =========================
   Interpretation hypotheses
   ========================= -/

inductive RosetteInterpretation : Type u
  | divine_symbol      -- standard: Inanna/Ishtar
  | heliocentric_system -- Sitchin-style: Sun + planets
  | other

structure IconHypothesis :=
  (rosette_interp   : RosetteInterpretation)
  (planet_count     : Option Nat)    -- if heliocentric, how many bodies?
  (extra_body_name  : Option String) -- e.g. "Nibiru"

class HypothesisConstraints (conv : AssyriologicalConventions) :=
  (admissible_rosette : RosetteInterpretation → Prop)
  (max_planets        : Nat)

instance va243_hypothesis_constraints (conv : AssyriologicalConventions) :
  HypothesisConstraints conv :=
  { admissible_rosette := fun r =>
      match r with
      | RosetteInterpretation.divine_symbol       => True
      | RosetteInterpretation.heliocentric_system =>
          -- conflicts with no_heliocentric_maps and max_naked_eye_planets
          False
      | RosetteInterpretation.other => True,
    max_planets := conv.max_naked_eye_planets }

def HypothesisValid (h : IconHypothesis) (g : IconGraph)
    (conv : AssyriologicalConventions) : Prop :=
  (HypothesisConstraints.admissible_rosette (va243_hypothesis_constraints conv) h.rosette_interp) ∧
  (match h.rosette_interp with
   | RosetteInterpretation.heliocentric_system =>
       match h.planet_count with
       | some n => n ≤ (va243_hypothesis_constraints conv).max_planets
       | none   => False
   | _ => True)

/- =========================
   Linking inscription + iconography
   ========================= -/

structure SealArtifact :=
  (inscription : Inscription)
  (icon        : IconGraph)

structure SealInterpretation :=
  (artifact   : SealArtifact)
  (hypothesis : IconHypothesis)
  (valid      : HypothesisValid hypothesis artifact.icon akkadian_conventions)

/- =========================
   Standard Assyriological reading
   ========================= -/

def va243_standard_hypothesis : IconHypothesis :=
  { rosette_interp  := RosetteInterpretation.divine_symbol,
    planet_count    := none,
    extra_body_name := none }

-- The standard hypothesis is admissible under conventions.
lemma va243_standard_admissible :
  HypothesisConstraints.admissible_rosette
    (va243_hypothesis_constraints akkadian_conventions)
    va243_standard_hypothesis.rosette_interp := by
  trivial   -- reduces to True by definition

/- =========================
   Sitchin-style hypothesis refutation
   ========================= -/

def va243_sitchin_hypothesis : IconHypothesis :=
  { rosette_interp  := RosetteInterpretation.heliocentric_system,
    planet_count    := some 11,
    extra_body_name := some "Nibiru" }

-- Sitchin hypothesis violates Assyriological constraints.
lemma va243_sitchin_inadmissible :
  ¬ HypothesisConstraints.admissible_rosette
      (va243_hypothesis_constraints akkadian_conventions)
      va243_sitchin_hypothesis.rosette_interp := by
  trivial   -- heliocentric_system → False under akkadian_conventions

/- =========================
   TODOs for full formalization
   ========================= -/
-- 1. Replace placeholder sign inventory with CDLI/Borger-based inductive family.
-- 2. Encode the actual VA 243 inscription as a concrete Inscription value.
-- 3. Build IconGraph from measured motif data (vector outlines, bounding boxes).
-- 4. Refine HypothesisValid with textual corpora constraints.
-- 5. Add decision procedures to automatically reject hypotheses.

end VA243

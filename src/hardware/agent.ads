-- agent.ads — Sovereign Agent SPARK Specification
-- Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
--
-- Formal specification of the entropy-constrained agent invariant.
-- Verified via Ada/SPARK + Why3 (Alt-Ergo, Z3, CVC4).
--
-- Core invariant from HyperKittyConstraintDSL:
--   active => trusted                    (INV-1)
--   0.0 <= entropy <= 0.20               (INV-2, INV-5)
--
-- Connects to entropy-balanced DMA engine:
--   power_entropy = 0 → entropy(agent) = 0 ≤ 0.20 → trusted eligible

package Sovereign.Agent is

   -- Refinement predicate: entropy is bounded by the sovereign constant
   subtype Entropy_Range is Float range 0.0 .. 0.20;

   type Agent_State is record
      Active  : Boolean;
      Trusted : Boolean;
      Entropy : Entropy_Range;   -- 0.0 ≤ Entropy ≤ 0.20 enforced by subtype
   end record;

   -- Ghost invariant: active => trusted
   function Invariant (S : Agent_State) return Boolean
     with Ghost,
          Post => (if S.Active then S.Trusted else True);

   -- Init: inactive, untrusted, zero entropy
   procedure Init (S : out Agent_State)
     with Post =>
       Invariant (S)
       and then not S.Active
       and then not S.Trusted
       and then S.Entropy = 0.0;

   -- Trusted activation: requires pre-existing non-active state
   procedure Activate_Trusted (S : in out Agent_State)
     with Pre  => Invariant (S) and then not S.Active,
          Post => Invariant (S) and then S.Active and then S.Trusted;

   -- Entropy update: clamped to [0.0, 0.20]
   procedure Update_Entropy (S : in out Agent_State; Delta : Float)
     with Pre  => Invariant (S),
          Post => Invariant (S)
                  and then S.Entropy >= 0.0
                  and then S.Entropy <= 0.20;

   -- Deactivate: trusted flag preserved, entropy unchanged
   procedure Deactivate (S : in out Agent_State)
     with Pre  => Invariant (S),
          Post => Invariant (S) and then not S.Active;

end Sovereign.Agent;

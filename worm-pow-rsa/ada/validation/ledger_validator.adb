--  Ledger_Validator body.
--  UNVERIFIED: has not been compiled or run.

package body Ledger_Validator with SPARK_Mode is

   --------------
   -- Validate --
   --------------

   function Validate
     (Prev    : Chain_Continuity.Record_Header;
      Current : Record_Input) return Verdict
   is
      Current_Header : constant Chain_Continuity.Record_Header :=
        (Sequence    => Current.Sequence,
         Prev_Hash   => Current.Prev_Hash,
         Record_Hash => Current.Record_Hash);
   begin
      --  1. Sequence continuity: sequence[n] = sequence[n-1] + 1.
      if not Chain_Continuity.Is_Sequence_Continuous
               (Prev.Sequence, Current.Sequence)
      then
         return Fail (Sequence_Gap);
      end if;

      --  2. Record ID correctness: caller-supplied ID must equal the
      --  independently-derived Expected_Record_ID (this package does
      --  not invent an ID derivation scheme; it trusts the caller's
      --  upstream derivation and only checks agreement).
      if Current.Record_ID /= Current.Expected_Record_ID then
         return Fail (Record_ID_Mismatch);
      end if;

      --  3. Payload hash correctness.
      if Current.Payload_Hash /= Current.Expected_Payload_Hash then
         return Fail (Payload_Hash_Mismatch);
      end if;

      --  4. prev_hash linkage: must equal predecessor's actual
      --  record_hash, not merely be internally consistent.
      if not Chain_Continuity.Is_Chain_Linked
               (Prev.Record_Hash, Current.Prev_Hash)
      then
         return Fail (Prev_Hash_Mismatch);
      end if;

      --  5. Proof-of-Work: recompute the header digest and check
      --  difficulty; never trust a caller-supplied "this passed PoW"
      --  flag.
      if not Proof_Of_Work.Verify_PoW
               (Current.PoW_Header_Value, Current.Difficulty)
      then
         return Fail (PoW_Invalid);
      end if;

      --  6. record_hash integrity: recompute SHA-256 over the canonical
      --  bytes (excluding record_hash) and compare.
      if not Chain_Continuity.Is_Record_Hash_Valid
               (Current.Canonical_Bytes_Excluding_Record_Hash
                  (1 .. Current.Canonical_Len),
                Current.Record_Hash)
      then
         return Fail (Record_Hash_Mismatch);
      end if;

      --  7. WORM append-only metadata: the storage layer must have
      --  accepted this as a genuine append at the current tail (see
      --  WORM_Store.Append_Result = Appended). This package does not
      --  perform the append itself — it only refuses to validate a
      --  record that was not actually appended in WORM fashion.
      if not Current.Is_WORM_Append then
         return Fail (WORM_Violation);
      end if;

      --  8. No sequence gaps: already guaranteed by check 1 for this
      --  single link; a caller validating a whole chain must call
      --  Validate once per consecutive pair, which transitively rules
      --  out gaps across the full sequence. (Kept as an explicit
      --  numbered check here for parity with the spec's checklist —
      --  check 1 IS this check for the two-record case.)

      return Pass;
   end Validate;

end Ledger_Validator;

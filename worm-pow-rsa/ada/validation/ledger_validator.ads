--  Ledger_Validator
--  Top-level validator that runs every check required to accept a WORM
--  ledger record: sequence correctness, record_id correctness, payload
--  hash, prev_hash linkage, PoW hash + difficulty, record_hash
--  integrity, WORM append-only metadata, and absence of sequence gaps.
--  Produces a single Valid/Invalid verdict with a specific reason code —
--  it NEVER silently repairs a bad record (no field is rewritten,
--  recomputed-and-substituted, or defaulted to make a check pass).
--
--  JSON syntax is assumed already parsed by an upstream layer; this
--  package consumes already-extracted fields (as canonical-form byte
--  strings and Hash_Hex values), consistent with the project brief.

with SHA256_Core;
with Chain_Continuity; use Chain_Continuity;
with Proof_Of_Work;    use Proof_Of_Work;

package Ledger_Validator with SPARK_Mode is

   subtype Hash_Hex is Chain_Continuity.Hash_Hex;

   --  All fields needed to validate one record against its predecessor.
   --  Record_ID is caller-defined opaque identifier text (e.g. a UUID or
   --  content-derived ID); this package checks it matches the expected
   --  derivation the caller supplies (Expected_Record_ID) rather than
   --  inventing its own ID scheme.
   type Record_Input is record
      Sequence           : Chain_Continuity.Sequence_Number;
      Record_ID          : Chain_Continuity.Hash_Hex;  --  reuse Hash_Hex
                                                          --  width as a
                                                          --  generic 64-
                                                          --  char ID slot
      Expected_Record_ID : Chain_Continuity.Hash_Hex;
      Prev_Hash          : Hash_Hex;
      Payload_Hash       : Hash_Hex;
      Expected_Payload_Hash : Hash_Hex;  --  recomputed by caller from
                                          --  the raw payload upstream;
                                          --  this package only compares
      Record_Hash        : Hash_Hex;
      Canonical_Bytes_Excluding_Record_Hash : String (1 .. 4096);
      Canonical_Len      : Natural range 0 .. 4096;
      PoW_Header_Value   : Proof_Of_Work.PoW_Header;
      Difficulty         : Proof_Of_Work.Difficulty_Level;
      Is_WORM_Append     : Boolean;  --  True iff the storage layer
                                     --  accepted this as an append at
                                     --  the current tail (see
                                     --  WORM_Store.Append_Result)
   end record;

   type Failure_Reason is
     (None,
      Sequence_Gap,
      Record_ID_Mismatch,
      Payload_Hash_Mismatch,
      Prev_Hash_Mismatch,
      PoW_Invalid,
      Record_Hash_Mismatch,
      WORM_Violation);

   type Verdict is record
      Valid  : Boolean;
      Reason : Failure_Reason;
   end record;

   Pass : constant Verdict := (Valid => True, Reason => None);

   function Fail (Reason : Failure_Reason) return Verdict is
     (Valid => False, Reason => Reason)
     with Pre => Reason /= None;

   --  Validate record Current against its immediate predecessor Prev.
   --  Every one of the eight checks listed in the package header comment
   --  runs; the FIRST failing check determines the returned Reason
   --  (checks run in a fixed, documented order so results are
   --  reproducible). No field is ever repaired — a mismatch is reported,
   --  not corrected.
   function Validate
     (Prev : Chain_Continuity.Record_Header;
      Current : Record_Input) return Verdict;

end Ledger_Validator;

--  Chain_Continuity
--  Formal invariants tying successive WORM ledger records together:
--    sequence[n] = sequence[n-1] + 1
--    prev_hash[n] = record_hash[n-1]
--    record_hash[n] = SHA256(canonical record[n] excluding record_hash)
--  These are the highest-value contracts in the system: SPARK Pre/Post
--  aspects make the continuity rules machine-checkable, not just
--  documented. Fail-closed throughout: every check function returns a
--  Boolean verdict computed from its inputs, never a hard-coded True.

with SHA256_Core;

package Chain_Continuity with SPARK_Mode is

   Hash_Hex_Len : constant := 64;
   subtype Hash_Hex is String (1 .. Hash_Hex_Len);

   subtype Sequence_Number is Natural;

   --  A minimal record header sufficient to check continuity; the full
   --  payload is opaque to this package (it only needs the previously
   --  computed record hash and sequence number, plus the canonical
   --  bytes to re-hash for record_hash verification).
   type Record_Header is record
      Sequence     : Sequence_Number;
      Prev_Hash    : Hash_Hex;
      Record_Hash  : Hash_Hex;  --  claimed hash of this record
   end record;

   --  Check 1: sequence continuity. Pure function of the two sequence
   --  numbers — the Post aspect states the invariant directly so any
   --  implementation error is caught by proof, not just by testing.
   function Is_Sequence_Continuous
     (Prev_Sequence, Sequence : Sequence_Number) return Boolean
   is (Sequence = Prev_Sequence + 1)
     with
       Global => null,
       Post   => Is_Sequence_Continuous'Result =
                   (Sequence = Prev_Sequence + 1);

   --  Check 2: hash-chain linkage. prev_hash[n] must equal the
   --  record_hash actually computed for record n-1 (Prev_Record_Hash),
   --  not merely whatever the current record claims.
   function Is_Chain_Linked
     (Prev_Record_Hash : Hash_Hex;
      Claimed_Prev_Hash : Hash_Hex) return Boolean
   is (Prev_Record_Hash = Claimed_Prev_Hash)
     with
       Global => null,
       Post   => Is_Chain_Linked'Result =
                   (Prev_Record_Hash = Claimed_Prev_Hash);

   --  Check 3: record_hash integrity. Recomputes SHA-256 over the
   --  supplied canonical bytes (which the caller must have assembled
   --  from the record's fields EXCLUDING the record_hash field itself,
   --  per RFC 8785-style canonicalization upstream) and compares
   --  against the claimed Record_Hash. Never trusts the claimed hash
   --  without recomputation.
   function Is_Record_Hash_Valid
     (Canonical_Bytes_Excluding_Hash : String;
      Claimed_Record_Hash            : Hash_Hex) return Boolean;

   --  Combined per-link check: all three invariants for record n given
   --  record n-1's header and record n's header plus n's canonical
   --  bytes (excluding record_hash).
   function Is_Link_Valid
     (Prev             : Record_Header;
      Current          : Record_Header;
      Current_Canonical_Bytes_Excluding_Hash : String) return Boolean
   is (Is_Sequence_Continuous (Prev.Sequence, Current.Sequence)
         and then Is_Chain_Linked (Prev.Record_Hash, Current.Prev_Hash)
         and then Is_Record_Hash_Valid
                    (Current_Canonical_Bytes_Excluding_Hash,
                     Current.Record_Hash))
     with Global => null;

   --  Whole-chain check result, distinguishing WHICH invariant broke and
   --  at what index, so callers never have to guess why a chain was
   --  rejected.
   type Break_Kind is
     (No_Break,
      Sequence_Gap,
      Hash_Link_Mismatch,
      Record_Hash_Mismatch);

   type Chain_Verdict is record
      Kind        : Break_Kind;
      Break_Index : Natural;  --  index (1-based, within the supplied
                               --  array) of the first record where the
                               --  break was detected; 0 if No_Break
   end record;

   Valid_Chain : constant Chain_Verdict := (Kind => No_Break, Break_Index => 0);

end Chain_Continuity;

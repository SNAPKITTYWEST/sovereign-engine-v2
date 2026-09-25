--  Cryptographic_Core
--  Top-level package tying together the SHA-256, RSA, canonicalization,
--  Proof-of-Work, continuity, WORM storage, and validation subsystems
--  into a single entry point for verifying one incoming ledger record.
--  This package performs no cryptography itself — it only sequences
--  calls into the specialized packages and forwards their fail-closed
--  verdicts unchanged. It never overrides a subordinate package's
--  UNKNOWN/INVALID result with an optimistic guess.

with SHA256_Core;
with RSA_Verify;
with Big_Num;
with Chain_Continuity;
with Proof_Of_Work;
with WORM_Store;
with Ledger_Validator;

package Cryptographic_Core with SPARK_Mode is

   --  Re-exported subsystem packages, so a caller can `with
   --  Cryptographic_Core;` and reach every subsystem via renames without
   --  needing to know the individual package names up front.
   package SHA256 renames SHA256_Core;
   package RSA renames RSA_Verify;
   package Continuity renames Chain_Continuity;
   package PoW renames Proof_Of_Work;
   package WORM renames WORM_Store;
   package Validation renames Ledger_Validator;

   --  Overall system status for a single record verification pass.
   --  Mirrors Ledger_Validator.Verdict but adds an explicit
   --  Signature_Status leg for the RSA check, since signature
   --  verification is orchestrated at this top level (the record's
   --  raw bytes and detached signature are not part of
   --  Ledger_Validator.Record_Input, which focuses on chain/PoW/WORM
   --  checks only).
   type Overall_Status is
     (Verified,               --  every check, including signature, passed
      Signature_Invalid,
      Signature_Malformed,
      Chain_Invalid,          --  see Ledger_Validator.Failure_Reason for detail
      Not_Verified);          --  fail-closed default; never produced by a
                               --  completed check — reserved for callers
                               --  representing "not yet checked"

   --  Verify a record's RSA signature (over its SHA-256 digest) AND run
   --  the full Ledger_Validator chain of checks. Returns Verified only
   --  if both the signature and every ledger invariant hold. Any
   --  failure anywhere short-circuits to the corresponding non-Verified
   --  status — no partial credit, no silent repair.
   function Verify_Record
     (Key              : RSA_Verify.Public_Key;
      Digest           : SHA256_Core.Digest_Type;
      Signature        : Big_Num.Unsigned_8_Array;
      Prev             : Chain_Continuity.Record_Header;
      Current          : Ledger_Validator.Record_Input) return Overall_Status;

end Cryptographic_Core;

--  Chain_Continuity body.
--  UNVERIFIED: has not been compiled or run. SPARK proof of the
--  Post aspects in the spec has not been discharged by gnatprove on
--  this machine (no toolchain installed) — treat contracts as
--  documentation-grade until proven.

package body Chain_Continuity with SPARK_Mode is

   ---------------------------
   -- Is_Record_Hash_Valid --
   ---------------------------

   function Is_Record_Hash_Valid
     (Canonical_Bytes_Excluding_Hash : String;
      Claimed_Record_Hash            : Hash_Hex) return Boolean
   is
      Computed : constant SHA256_Core.Hex_Digest_String :=
        SHA256_Core.Hash_Hex (Canonical_Bytes_Excluding_Hash);
   begin
      return Computed = Claimed_Record_Hash;
   end Is_Record_Hash_Valid;

end Chain_Continuity;

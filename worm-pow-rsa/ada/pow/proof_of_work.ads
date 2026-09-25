--  Proof_Of_Work
--  Constructs and verifies the WORM chain's proof-of-work headers.
--  Header shape: { sequence, prev_hash, payload_hash, timestamp, nonce }
--  canonicalized via Canonical_JSON and hashed with SHA-256. Difficulty
--  is expressed as a count of required leading hex-zero nibbles in the
--  resulting digest.

with SHA256_Core;
with Canonical_JSON;

package Proof_Of_Work with SPARK_Mode is

   Hash_Hex_Len : constant := 64;  --  SHA-256 hex digest length
   subtype Hash_Hex is String (1 .. Hash_Hex_Len);

   Max_Difficulty : constant := 16;  --  16 nibbles = full 64-bit prefix
   subtype Difficulty_Level is Natural range 0 .. Max_Difficulty;

   --  Search is deterministic and starts at nonce 0; callers pick an
   --  upper bound appropriate to their environment (this package does
   --  not loop forever).
   Default_Max_Nonce : constant := 50_000_000;

   type PoW_Header is record
      Sequence     : Natural;
      Prev_Hash    : Hash_Hex;
      Payload_Hash : Hash_Hex;
      Timestamp    : Natural;  --  Unix seconds; caller-supplied, this
                                --  package does not read the system clock
      Nonce        : Natural;
   end record;

   type Search_Result is (Found, Exhausted, Canonicalization_Failed);

   --  Render Header to its canonical JSON form and return the SHA-256
   --  hex digest of that form. Fails closed (Success = False) if
   --  canonicalization fails (e.g. malformed hash strings supplied).
   procedure Header_Digest
     (Header  : PoW_Header;
      Digest  : out Hash_Hex;
      Success : out Boolean);

   --  True iff Digest has at least Difficulty leading hex-zero nibbles.
   function Meets_Difficulty
     (Digest     : Hash_Hex;
      Difficulty : Difficulty_Level) return Boolean;

   --  Deterministic nonce search: starting at Header.Nonce = 0, try
   --  successive nonces up to Max_Nonce, returning the first that meets
   --  Difficulty. Never fabricates a result: Exhausted means no valid
   --  nonce was found within the search bound, and the caller must not
   --  treat that as success.
   procedure Find_Nonce
     (Base_Header : PoW_Header;
      Difficulty  : Difficulty_Level;
      Max_Nonce   : Natural := Default_Max_Nonce;
      Result      : out Search_Result;
      Found_Nonce : out Natural;
      Found_Digest : out Hash_Hex);

   --  Verify that Header's declared Nonce actually produces a digest
   --  meeting Difficulty. This recomputes the digest — it never trusts
   --  a caller-supplied digest value.
   function Verify_PoW
     (Header     : PoW_Header;
      Difficulty : Difficulty_Level) return Boolean;

end Proof_Of_Work;

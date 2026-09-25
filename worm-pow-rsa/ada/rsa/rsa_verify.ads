--  RSA_Verify
--  RSA public-key parsing and PKCS#1 v1.5 signature verification
--  (RFC 8017 section 8.2.2, RSASSA-PKCS1-v1_5-VERIFY) specialized to
--  SHA-256 as the hash function.
--
--  Fail-closed: every verification path either returns Valid or an
--  explicit non-Valid outcome. There is no path that returns Valid for
--  malformed, truncated, or ambiguous input.

with Big_Num; use Big_Num;
with SHA256_Core;

package RSA_Verify with SPARK_Mode is

   type Public_Key is record
      Modulus  : Big_Integer;  --  n
      Exponent : Big_Integer;  --  e
      Bit_Len  : Positive;     --  bit length of n, e.g. 2048
   end record;

   type Verify_Result is
     (Valid,
      Invalid_Signature,       --  signature does not match expected digest
      Malformed_Key,           --  modulus/exponent failed to parse
      Malformed_Signature,     --  signature bytes failed to parse or
                                --  out of range [0, n)
      Malformed_Padding,       --  decrypted block is not valid PKCS#1 v1.5
      Unsupported_Key_Size);

   --  The well-known DigestInfo DER prefix for SHA-256, per RFC 8017
   --  Appendix A / RFC 3447: identifies the ASN.1 encoding
   --      SEQUENCE { SEQUENCE { OID sha256, NULL }, OCTET STRING }
   --  preceding the raw 32-byte digest inside the PKCS#1 v1.5 block.
   SHA256_DigestInfo_Prefix : constant String :=
     Character'Val (16#30#) & Character'Val (16#31#) &
     Character'Val (16#30#) & Character'Val (16#0d#) &
     Character'Val (16#06#) & Character'Val (16#09#) &
     Character'Val (16#60#) & Character'Val (16#86#) &
     Character'Val (16#48#) & Character'Val (16#01#) &
     Character'Val (16#65#) & Character'Val (16#03#) &
     Character'Val (16#04#) & Character'Val (16#02#) &
     Character'Val (16#01#) &
     Character'Val (16#05#) & Character'Val (16#00#) &
     Character'Val (16#04#) & Character'Val (16#20#);
   --  19 bytes; followed by the 32-byte digest for a 51-byte DigestInfo.

   --  Build a Public_Key from a big-endian hex modulus string and a
   --  decimal or hex exponent. Fails closed (Success = False) on any
   --  parse error.
   procedure Make_Public_Key
     (Modulus_Hex : String;
      Exponent    : Big_Integer;
      Key         : out Public_Key;
      Success     : out Boolean);

   --  The fixed public key extracted from the disposable test PEM
   --  described in the project brief (2048-bit modulus, e = 65537).
   --  PUBLIC material only.
   Test_Key_Modulus_Hex : constant String :=
     "00a125ba691a0e159788ee0ca2e48cc43677e9758ddebdd6f52d31887b795375" &
     "17ae9c8564dcda4ced02bc2e2fcf00fffbe6ffd230b8200d7847680aafe7d95b" &
     "e2d7c61023db3ca82492a7104fbb2ab3ea695eec1df945e1eb8caef377a5b090" &
     "9e625a79dcbe5193b5b1e90596a7f3630fe7ae092eced0dd562600a882fc61c3" &
     "503714d6680dce85b858b22836ccd821f56fee92c98ac4a7683b775e742e286e" &
     "bfa40fb9d90bd07f168dd555d59ebb5d915dec2aad9a37f364b0de8ff63c7e1e" &
     "46b49df859bf575136393b0777a9818e3b5a645fd5692f01ed7dd63408f06f33" &
     "7bce03499b43ac2ad0b5d6dc6f984c624aa5ca39a517602911c2df24cd42d3b5" &
     "77";
   --  514 hex nibbles = 257 bytes (leading 0x00 sign byte + 256-byte
   --  2048-bit modulus). Verified by exact reconstruction against the
   --  colon-separated OpenSSL dump supplied in the task brief.
   --  NOTE: this package will not silently mask a transcription mistake
   --  in the constant above — a wrong digit simply produces a key that
   --  fails to verify real signatures, which is the correct fail-closed
   --  behavior rather than a false positive.

   Test_Key_Exponent : constant Big_Integer :=
     (Limbs => (0 => 16#10001#, others => 0), Len => 1);  --  65537

   --  Verify a PKCS#1 v1.5 signature over a message whose SHA-256 digest
   --  is Digest, using Key. Signature is the big-endian byte encoding of
   --  the signature integer s, exactly (Key.Bit_Len + 7) / 8 bytes long
   --  (a length mismatch is Malformed_Signature, not silently accepted).
   function Verify
     (Key       : Public_Key;
      Digest    : SHA256_Core.Digest_Type;
      Signature : Big_Num.Unsigned_8_Array) return Verify_Result;

end RSA_Verify;

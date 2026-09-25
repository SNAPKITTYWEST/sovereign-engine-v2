--  Big_Num
--  Minimal arbitrary-precision unsigned integer arithmetic sufficient for
--  2048-bit RSA public-key verification (modular exponentiation via
--  square-and-multiply, using schoolbook multiplication and division).
--  This is NOT a general-purpose bignum library and is NOT constant-time;
--  it is intended only for verifying PUBLIC signatures (no secret-dependent
--  branching concerns apply to public-exponent operations).

with Interfaces; use Interfaces;

package Big_Num with SPARK_Mode is

   --  Limb = 32-bit word; a 2048-bit number needs 64 limbs. We size for up
   --  to 4096 bits (128 limbs) to allow headroom for intermediate products
   --  during modular reduction.
   Max_Limbs : constant := 128;

   subtype Limb_Index is Natural range 0 .. Max_Limbs - 1;
   type Limb_Array is array (Limb_Index) of Unsigned_32;

   --  A Big_Integer stores limbs little-endian (Limbs (0) is least
   --  significant) plus an explicit used-length so trailing zero limbs
   --  are not significant.
   type Big_Integer is record
      Limbs : Limb_Array := (others => 0);
      Len   : Natural range 0 .. Max_Limbs := 0;  --  number of significant limbs
   end record;

   Zero : constant Big_Integer := (Limbs => (others => 0), Len => 0);

   function Is_Zero (X : Big_Integer) return Boolean is
     (X.Len = 0);

   type Unsigned_8_Array is array (Natural range <>) of Unsigned_8;

   --  Parse a big-endian hex string (colon- or non-separated, case
   --  insensitive) into a Big_Integer. Returns Zero-length result with
   --  Success = False on any malformed character — fail closed, never
   --  guess at a partially-parsed value.
   procedure From_Hex
     (Hex     : String;
      Result  : out Big_Integer;
      Success : out Boolean);

   --  Parse a big-endian byte buffer (e.g. a signature) into a Big_Integer.
   procedure From_Bytes
     (Bytes   : Unsigned_8_Array;
      Result  : out Big_Integer;
      Success : out Boolean);

   --  Render as a big-endian byte array of exactly Byte_Len bytes,
   --  zero-padded on the left. Success is False if X does not fit.
   procedure To_Bytes
     (X        : Big_Integer;
      Byte_Len : Positive;
      Result   : out Unsigned_8_Array;
      Success  : out Boolean)
     with Pre => Result'Length = Byte_Len;

   function "<" (A, B : Big_Integer) return Boolean;
   function "=" (A, B : Big_Integer) return Boolean;
   function ">=" (A, B : Big_Integer) return Boolean is (not (A < B));

   --  Modular exponentiation: Base^Exp mod Modulus.
   --  Fails closed (returns Zero, Success => False) if Modulus is zero.
   procedure Mod_Pow
     (Base    : Big_Integer;
      Exp     : Big_Integer;
      Modulus : Big_Integer;
      Result  : out Big_Integer;
      Success : out Boolean);

end Big_Num;

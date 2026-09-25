--  Big_Num body.
--  UNVERIFIED: schoolbook long-division and multiplication implemented by
--  hand; has not been run against known-answer test vectors. Review before
--  trusting in production. Not constant-time (acceptable: all operations
--  here are on PUBLIC values only — modulus, exponent, signature).

package body Big_Num with SPARK_Mode is

   --  Strip trailing (high-order) zero limbs to normalize Len.
   procedure Normalize (X : in out Big_Integer) is
   begin
      while X.Len > 0 and then X.Limbs (X.Len - 1) = 0 loop
         X.Len := X.Len - 1;
      end loop;
   end Normalize;

   function "=" (A, B : Big_Integer) return Boolean is
      Aa : Big_Integer := A;
      Bb : Big_Integer := B;
   begin
      Normalize (Aa);
      Normalize (Bb);
      if Aa.Len /= Bb.Len then
         return False;
      end if;
      for I in 0 .. Aa.Len - 1 loop
         if Aa.Limbs (I) /= Bb.Limbs (I) then
            return False;
         end if;
      end loop;
      return True;
   end "=";

   function "<" (A, B : Big_Integer) return Boolean is
      Aa : Big_Integer := A;
      Bb : Big_Integer := B;
   begin
      Normalize (Aa);
      Normalize (Bb);
      if Aa.Len /= Bb.Len then
         return Aa.Len < Bb.Len;
      end if;
      for I in reverse 0 .. Aa.Len - 1 loop
         if Aa.Limbs (I) /= Bb.Limbs (I) then
            return Aa.Limbs (I) < Bb.Limbs (I);
         end if;
      end loop;
      return False;  --  equal
   end "<";

   ---------------
   -- From_Hex --
   ---------------

   procedure From_Hex
     (Hex     : String;
      Result  : out Big_Integer;
      Success : out Boolean)
   is
      --  Filter out ':' and whitespace separators, collect hex nibbles.
      Nibbles : String (1 .. Hex'Length);
      NCount  : Natural := 0;
   begin
      Result  := Zero;
      Success := True;

      for I in Hex'Range loop
         declare
            Ch : constant Character := Hex (I);
         begin
            if Ch = ':' or Ch = ' ' or Ch = ASCII.LF or Ch = ASCII.CR
              or Ch = ASCII.HT
            then
               null;  --  skip separator
            elsif (Ch in '0' .. '9') or (Ch in 'a' .. 'f')
              or (Ch in 'A' .. 'F')
            then
               NCount := NCount + 1;
               Nibbles (NCount) := Ch;
            else
               Success := False;
               return;
            end if;
         end;
      end loop;

      if NCount = 0 then
         Success := False;
         return;
      end if;

      --  Need an even number of nibbles to form whole bytes.
      if NCount mod 2 /= 0 then
         Success := False;
         return;
      end if;

      declare
         Byte_Count : constant Natural := NCount / 2;
         Bytes      : Unsigned_8_Array (0 .. Byte_Count - 1);

         function Nibble_Val (C : Character) return Unsigned_8 is
           (case C is
              when '0' .. '9' => Character'Pos (C) - Character'Pos ('0'),
              when 'a' .. 'f' => Character'Pos (C) - Character'Pos ('a') + 10,
              when 'A' .. 'F' => Character'Pos (C) - Character'Pos ('A') + 10,
              when others     => 0);
      begin
         for B in 0 .. Byte_Count - 1 loop
            Bytes (B) :=
              (Nibble_Val (Nibbles (B * 2 + 1)) * 16) +
              Nibble_Val (Nibbles (B * 2 + 2));
         end loop;
         From_Bytes (Bytes, Result, Success);
      end;
   end From_Hex;

   -----------------
   -- From_Bytes --
   -----------------

   procedure From_Bytes
     (Bytes   : Unsigned_8_Array;
      Result  : out Big_Integer;
      Success : out Boolean)
   is
   begin
      Result  := Zero;
      Success := True;

      if Bytes'Length = 0 then
         return;  --  value 0, Success remains True
      end if;

      if (Bytes'Length + 3) / 4 > Max_Limbs then
         Success := False;
         return;
      end if;

      --  Bytes are big-endian; process from least-significant (last) byte.
      declare
         Idx      : Integer := Bytes'Last;
         Limb_Pos : Natural := 0;
      begin
         while Idx >= Bytes'First loop
            declare
               Limb : Unsigned_32 := 0;
               Shift : Natural := 0;
               J : Integer := Idx;
               Count : Natural := 0;
            begin
               while J >= Bytes'First and then Count < 4 loop
                  Limb := Limb or Shift_Left (Unsigned_32 (Bytes (J)), Shift);
                  Shift := Shift + 8;
                  J := J - 1;
                  Count := Count + 1;
               end loop;
               Result.Limbs (Limb_Pos) := Limb;
               Idx := J;
               Limb_Pos := Limb_Pos + 1;
            end;
         end loop;
         Result.Len := Limb_Pos;
      end;

      Normalize (Result);
   end From_Bytes;

   ---------------
   -- To_Bytes --
   ---------------

   procedure To_Bytes
     (X        : Big_Integer;
      Byte_Len : Positive;
      Result   : out Unsigned_8_Array;
      Success  : out Boolean)
   is
      Xn : Big_Integer := X;
   begin
      Normalize (Xn);
      Result := (others => 0);

      if Natural (Xn.Len) * 4 > Byte_Len + 3 then
         --  Could still fit if high limb has few significant bytes;
         --  do a precise check below instead of bailing here.
         null;
      end if;

      declare
         Pos : Integer := Result'Last;
      begin
         for I in 0 .. Xn.Len - 1 loop
            declare
               L : constant Unsigned_32 := Xn.Limbs (I);
            begin
               for B in 0 .. 3 loop
                  if Pos < Result'First then
                     --  Overflow: remaining nonzero bytes don't fit.
                     if Shift_Right (L, B * 8) and 16#FF# /= 0 then
                        Success := False;
                        return;
                     end if;
                  else
                     Result (Pos) :=
                       Unsigned_8 (Shift_Right (L, B * 8) and 16#FF#);
                     Pos := Pos - 1;
                  end if;
               end loop;
            end;
         end loop;
      end;

      Success := True;
   end To_Bytes;

   --  Compare and subtract helpers for division ---------------------------

   procedure Sub_In_Place (A : in out Big_Integer; B : Big_Integer)
     --  Precondition (checked by caller): A >= B.
   is
      Borrow : Integer_32 := 0;
      Len    : constant Natural := A.Len;
   begin
      for I in 0 .. Len - 1 loop
         declare
            Bv : constant Unsigned_32 :=
              (if I < B.Len then B.Limbs (I) else 0);
            Diff : Integer_64 :=
              Integer_64 (A.Limbs (I)) - Integer_64 (Bv) - Integer_64 (Borrow);
         begin
            if Diff < 0 then
               Diff := Diff + 2 ** 32;
               Borrow := 1;
            else
               Borrow := 0;
            end if;
            A.Limbs (I) := Unsigned_32 (Diff);
         end;
      end loop;
      Normalize (A);
   end Sub_In_Place;

   --  Shift-left by one bit, in place, growing Len as needed.
   procedure Shift_Left_One (X : in out Big_Integer) is
      Carry : Unsigned_32 := 0;
   begin
      for I in 0 .. X.Len - 1 loop
         declare
            New_Carry : constant Unsigned_32 :=
              Shift_Right (X.Limbs (I), 31);
         begin
            X.Limbs (I) := Shift_Left (X.Limbs (I), 1) or Carry;
            Carry := New_Carry;
         end;
      end loop;
      if Carry /= 0 and then X.Len < Max_Limbs then
         X.Limbs (X.Len) := Carry;
         X.Len := X.Len + 1;
      end if;
   end Shift_Left_One;

   --  Multiply two Big_Integers, result truncated/rejected if it would
   --  exceed Max_Limbs (Success flag). Used inside Mod_Pow only with
   --  operands already reduced modulo Modulus, whose product fits within
   --  2 * Modulus limb-width <= Max_Limbs by construction (Modulus <= 64
   --  limbs for up to 2048-bit keys, headroom to 128 limbs).
   procedure Mul
     (A, B    : Big_Integer;
      Result  : out Big_Integer;
      Success : out Boolean)
   is
      Acc : Limb_Array := (others => 0);
      Acc_Len : Natural := 0;
   begin
      Success := True;
      Result := Zero;

      if Is_Zero (A) or else Is_Zero (B) then
         return;
      end if;

      if A.Len + B.Len > Max_Limbs then
         Success := False;
         return;
      end if;

      declare
         type Wide_Array is array (0 .. Max_Limbs) of Unsigned_64;
         Wide : Wide_Array := (others => 0);
      begin
         for I in 0 .. A.Len - 1 loop
            if A.Limbs (I) /= 0 then
               declare
                  Carry : Unsigned_64 := 0;
               begin
                  for J in 0 .. B.Len - 1 loop
                     declare
                        Prod : constant Unsigned_64 :=
                          Unsigned_64 (A.Limbs (I)) * Unsigned_64 (B.Limbs (J))
                          + Wide (I + J) + Carry;
                     begin
                        Wide (I + J) := Prod and 16#FFFF_FFFF#;
                        Carry := Shift_Right (Prod, 32);
                     end;
                  end loop;
                  --  propagate remaining carry
                  declare
                     K : Natural := I + B.Len;
                  begin
                     while Carry > 0 loop
                        declare
                           Sum : constant Unsigned_64 :=
                             Wide (K) + Carry;
                        begin
                           Wide (K) := Sum and 16#FFFF_FFFF#;
                           Carry := Shift_Right (Sum, 32);
                        end;
                        K := K + 1;
                     end loop;
                  end;
               end;
            end if;
         end loop;

         Acc_Len := A.Len + B.Len;
         if Acc_Len > Max_Limbs then
            Success := False;
            return;
         end if;
         for I in 0 .. Acc_Len - 1 loop
            Acc (I) := Unsigned_32 (Wide (I));
         end loop;
      end;

      Result.Limbs := Acc;
      Result.Len := Acc_Len;
      Normalize (Result);
   end Mul;

   --  Modulo via repeated shift-and-subtract (binary long division).
   --  Correct but not fast; adequate for verification-only use (a handful
   --  of Mod_Pow calls per signature check, not a hot loop).
   procedure Mod_Reduce
     (X       : Big_Integer;
      Modulus : Big_Integer;
      Result  : out Big_Integer)
   is
      Rem_Val : Big_Integer := Zero;
   begin
      if X.Len = 0 then
         Result := Zero;
         return;
      end if;

      --  Process bits of X from most significant to least significant.
      for I in reverse 0 .. X.Len - 1 loop
         for Bit in reverse 0 .. 31 loop
            Shift_Left_One (Rem_Val);
            if (Shift_Right (X.Limbs (I), Bit) and 1) = 1 then
               if Rem_Val.Len = 0 then
                  Rem_Val.Limbs (0) := 1;
                  Rem_Val.Len := 1;
               else
                  Rem_Val.Limbs (0) := Rem_Val.Limbs (0) or 1;
               end if;
            end if;
            if not (Rem_Val < Modulus) then
               Sub_In_Place (Rem_Val, Modulus);
            end if;
         end loop;
      end loop;

      Result := Rem_Val;
   end Mod_Reduce;

   -------------
   -- Mod_Pow --
   -------------

   procedure Mod_Pow
     (Base    : Big_Integer;
      Exp     : Big_Integer;
      Modulus : Big_Integer;
      Result  : out Big_Integer;
      Success : out Boolean)
   is
      B          : Big_Integer;
      R          : Big_Integer := Zero;
      Mul_Result : Big_Integer;
      Mul_Ok     : Boolean;
   begin
      Result  := Zero;
      Success := True;

      if Is_Zero (Modulus) then
         Success := False;
         return;
      end if;

      if Modulus.Len = 1 and then Modulus.Limbs (0) = 1 then
         --  mod 1 is always 0
         Result := Zero;
         return;
      end if;

      --  R := 1
      R.Limbs (0) := 1;
      R.Len := 1;

      --  B := Base mod Modulus
      Mod_Reduce (Base, Modulus, B);

      if Exp.Len = 0 then
         --  x^0 = 1 mod n (n > 1, already checked above)
         Result := R;
         return;
      end if;

      --  Square-and-multiply, scanning exponent bits MSB to LSB.
      for I in reverse 0 .. Exp.Len - 1 loop
         for Bit in reverse 0 .. 31 loop
            --  Skip leading zero bits above the highest set bit of the
            --  top limb (harmless: squaring 1 repeatedly keeps R = 1).
            Mul (R, R, Mul_Result, Mul_Ok);
            if not Mul_Ok then
               Success := False;
               return;
            end if;
            Mod_Reduce (Mul_Result, Modulus, R);

            if (Shift_Right (Exp.Limbs (I), Bit) and 1) = 1 then
               Mul (R, B, Mul_Result, Mul_Ok);
               if not Mul_Ok then
                  Success := False;
                  return;
               end if;
               Mod_Reduce (Mul_Result, Modulus, R);
            end if;
         end loop;
      end loop;

      Result := R;
   end Mod_Pow;

end Big_Num;

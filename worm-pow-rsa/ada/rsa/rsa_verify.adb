--  RSA_Verify body.
--  UNVERIFIED: has not been compiled or tested against a real
--  signature produced by the corresponding private key.

with Interfaces; use Interfaces;

package body RSA_Verify with SPARK_Mode is

   ----------------------
   -- Make_Public_Key --
   ----------------------

   procedure Make_Public_Key
     (Modulus_Hex : String;
      Exponent    : Big_Integer;
      Key         : out Public_Key;
      Success     : out Boolean)
   is
      N : Big_Integer;
      Ok : Boolean;
   begin
      Key := (Modulus => Zero, Exponent => Zero, Bit_Len => 1);
      Success := False;

      From_Hex (Modulus_Hex, N, Ok);
      if not Ok or else Is_Zero (N) then
         return;
      end if;

      if Is_Zero (Exponent) then
         return;
      end if;

      --  Compute bit length of N.
      declare
         Bits : Natural := 0;
      begin
         for I in reverse 0 .. N.Len - 1 loop
            if N.Limbs (I) /= 0 then
               declare
                  Top : Unsigned_32 := N.Limbs (I);
                  B   : Natural := 0;
               begin
                  while Top /= 0 loop
                     Top := Shift_Right (Top, 1);
                     B := B + 1;
                  end loop;
                  Bits := I * 32 + B;
               end;
               exit;
            end if;
         end loop;

         if Bits = 0 then
            return;
         end if;

         Key := (Modulus => N, Exponent => Exponent, Bit_Len => Bits);
         Success := True;
      end;
   end Make_Public_Key;

   ---------------
   -- Constant-time-ish byte compare (public data only; not secret) --
   ---------------

   function Bytes_Equal (A, B : String) return Boolean is
   begin
      if A'Length /= B'Length then
         return False;
      end if;
      for I in 0 .. A'Length - 1 loop
         if A (A'First + I) /= B (B'First + I) then
            return False;
         end if;
      end loop;
      return True;
   end Bytes_Equal;

   ------------
   -- Verify --
   ------------

   function Verify
     (Key       : Public_Key;
      Digest    : SHA256_Core.Digest_Type;
      Signature : Big_Num.Unsigned_8_Array) return Verify_Result
   is
      Expected_Byte_Len : constant Positive := (Key.Bit_Len + 7) / 8;
      S    : Big_Integer;
      S_Ok : Boolean;
      M    : Big_Integer;
      M_Ok : Boolean;
      EM   : Unsigned_8_Array (0 .. Expected_Byte_Len - 1);
      EM_Ok : Boolean;
   begin
      if Is_Zero (Key.Modulus) or else Is_Zero (Key.Exponent) then
         return Malformed_Key;
      end if;

      if Signature'Length /= Expected_Byte_Len then
         return Malformed_Signature;
      end if;

      From_Bytes (Signature, S, S_Ok);
      if not S_Ok then
         return Malformed_Signature;
      end if;

      --  Signature representative must satisfy 0 <= s < n (RFC 8017 5.2.2).
      if Is_Zero (S) or else not (S < Key.Modulus) then
         return Malformed_Signature;
      end if;

      --  m = s^e mod n
      Mod_Pow (S, Key.Exponent, Key.Modulus, M, M_Ok);
      if not M_Ok then
         return Malformed_Key;
      end if;

      --  Encode m as EM, exactly Expected_Byte_Len bytes (RFC 8017 5.2.2
      --  I2OSP). If m does not fit (shouldn't happen since m < n and n
      --  has Expected_Byte_Len bytes), fail closed.
      To_Bytes (M, Expected_Byte_Len, EM, EM_Ok);
      if not EM_Ok then
         return Malformed_Signature;
      end if;

      --  Verify PKCS#1 v1.5 padding structure (RFC 8017 9.2, EMSA-PKCS1-v1_5):
      --    EM = 0x00 || 0x01 || PS || 0x00 || T
      --  where PS is >= 8 bytes of 0xFF, and T is the DER DigestInfo for
      --  SHA-256 followed by the 32-byte digest.
      if EM'Length < 11 + SHA256_DigestInfo_Prefix'Length + 32 then
         return Malformed_Padding;
      end if;

      if EM (EM'First) /= 0 or else EM (EM'First + 1) /= 1 then
         return Malformed_Padding;
      end if;

      declare
         T_Len   : constant Natural :=
           SHA256_DigestInfo_Prefix'Length + 32;
         PS_End  : Natural;  --  index (0-based within EM) of the 0x00
                              --  separator after the PS padding run
         Pos     : Natural := EM'First + 2;
         Found_Sep : Boolean := False;
      begin
         --  Walk the 0xFF padding run; must be at least 8 bytes.
         declare
             FF_Count : Natural := 0;
         begin
            while Pos <= EM'Last loop
               exit when EM (Pos) = 0;
               if EM (Pos) /= 16#FF# then
                  return Malformed_Padding;
               end if;
               FF_Count := FF_Count + 1;
               Pos := Pos + 1;
            end loop;

            if Pos > EM'Last or else EM (Pos) /= 0 then
               return Malformed_Padding;
            end if;

            if FF_Count < 8 then
               return Malformed_Padding;
            end if;

            Found_Sep := True;
            PS_End := Pos;  --  index of the 0x00 separator
         end;

         if not Found_Sep then
            return Malformed_Padding;
         end if;

         declare
            T_Start : constant Natural := PS_End + 1;
         begin
            if T_Start + T_Len - 1 /= EM'Last then
               --  T must run exactly to the end of EM — no trailing
               --  garbage permitted.
               return Malformed_Padding;
            end if;

            --  Compare DigestInfo prefix.
            for I in 0 .. SHA256_DigestInfo_Prefix'Length - 1 loop
               if Character'Pos (SHA256_DigestInfo_Prefix
                                    (SHA256_DigestInfo_Prefix'First + I))
                 /= Integer (EM (T_Start + I))
               then
                  return Malformed_Padding;
               end if;
            end loop;

            --  Compare the raw digest bytes.
            declare
               Digest_Start : constant Natural :=
                 T_Start + SHA256_DigestInfo_Prefix'Length;
            begin
               for I in SHA256_Core.Digest_Index loop
                  if EM (Digest_Start + I) /= Digest (I) then
                     return Invalid_Signature;
                  end if;
               end loop;
            end;
         end;
      end;

      return Valid;
   end Verify;

end RSA_Verify;

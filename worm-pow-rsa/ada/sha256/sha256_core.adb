--  SHA256_Core body: FIPS 180-4 section 6.2 implementation.
--  UNVERIFIED: has not been compiled, run, or tested against known-answer
--  vectors on this machine. Review against RFC 6234 / FIPS 180-4 test
--  vectors before trusting in production.

package body SHA256_Core with SPARK_Mode is

   --  Round constants (FIPS 180-4 4.2.2), first 32 bits of the fractional
   --  parts of the cube roots of the first 64 primes.
   K : constant array (0 .. 63) of Unsigned_32 :=
     (16#428a2f98#, 16#71374491#, 16#b5c0fbcf#, 16#e9b5dba5#,
      16#3956c25b#, 16#59f111f1#, 16#923f82a4#, 16#ab1c5ed5#,
      16#d807aa98#, 16#12835b01#, 16#243185be#, 16#550c7dc3#,
      16#72be5d74#, 16#80deb1fe#, 16#9bdc06a7#, 16#c19bf174#,
      16#e49b69c1#, 16#efbe4786#, 16#0fc19dc6#, 16#240ca1cc#,
      16#2de92c6f#, 16#4a7484aa#, 16#5cb0a9dc#, 16#76f988da#,
      16#983e5152#, 16#a831c66d#, 16#b00327c8#, 16#bf597fc7#,
      16#c6e00bf3#, 16#d5a79147#, 16#06ca6351#, 16#14292967#,
      16#27b70a85#, 16#2e1b2138#, 16#4d2c6dfc#, 16#53380d13#,
      16#650a7354#, 16#766a0abb#, 16#81c2c92e#, 16#92722c85#,
      16#a2bfe8a1#, 16#a81a664b#, 16#c24b8b70#, 16#c76c51a3#,
      16#d192e819#, 16#d6990624#, 16#f40e3585#, 16#106aa070#,
      16#19a4c116#, 16#1e376c08#, 16#2748774c#, 16#34b0bcb5#,
      16#391c0cb3#, 16#4ed8aa4a#, 16#5b9cca4f#, 16#682e6ff3#,
      16#748f82ee#, 16#78a5636f#, 16#84c87814#, 16#8cc70208#,
      16#90befffa#, 16#a4506ceb#, 16#bef9a3f7#, 16#c67178f2#);

   H_Init : constant array (0 .. 7) of Unsigned_32 :=
     (16#6a09e667#, 16#bb67ae85#, 16#3c6ef372#, 16#a54ff53a#,
      16#510e527f#, 16#9b05688c#, 16#1f83d9ab#, 16#5be0cd19#);

   function Rotr (X : Unsigned_32; N : Natural) return Unsigned_32 is
     (Rotate_Right (X, N));

   function Small_Sigma0 (X : Unsigned_32) return Unsigned_32 is
     (Rotr (X, 7) xor Rotr (X, 18) xor Shift_Right (X, 3));

   function Small_Sigma1 (X : Unsigned_32) return Unsigned_32 is
     (Rotr (X, 17) xor Rotr (X, 19) xor Shift_Right (X, 10));

   function Big_Sigma0 (X : Unsigned_32) return Unsigned_32 is
     (Rotr (X, 2) xor Rotr (X, 13) xor Rotr (X, 22));

   function Big_Sigma1 (X : Unsigned_32) return Unsigned_32 is
     (Rotr (X, 6) xor Rotr (X, 11) xor Rotr (X, 25));

   function Ch (X, Y, Z : Unsigned_32) return Unsigned_32 is
     ((X and Y) xor ((not X) and Z));

   function Maj (X, Y, Z : Unsigned_32) return Unsigned_32 is
     ((X and Y) xor (X and Z) xor (Y and Z));

   ----------
   -- Hash --
   ----------

   function Hash (Data : Stream_Element_Array) return Digest_Type is
      Msg_Len_Bits : constant Unsigned_64 :=
        Unsigned_64 (Data'Length) * 8;

      --  Padded length: original + 1 (0x80 byte) + zeros + 8 (length),
      --  rounded up to a multiple of 64 bytes.
      Pad_Zeros : Natural;
      Total_Len : Natural;
   begin
      declare
         Rem_Len : constant Natural :=
           Natural ((Data'Length + 9) mod 64);
      begin
         if Rem_Len = 0 then
            Pad_Zeros := 0;
         else
            Pad_Zeros := 64 - Rem_Len;
         end if;
      end;

      Total_Len := Data'Length + 1 + Pad_Zeros + 8;

      declare
         Msg : Stream_Element_Array (0 .. Stream_Element_Offset (Total_Len - 1))
           := (others => 0);
         H   : array (0 .. 7) of Unsigned_32 := H_Init;
         Idx : Stream_Element_Offset := 0;
      begin
         --  Copy original message.
         for I in Data'Range loop
            Msg (Idx) := Data (I);
            Idx := Idx + 1;
         end loop;

         --  Append the mandatory 0x80 byte.
         Msg (Idx) := 16#80#;
         Idx := Idx + 1;

         --  Zero padding is already in place (Msg initialized to 0).
         --  Append 64-bit big-endian length in bits at the end.
         declare
            Len_Pos : constant Stream_Element_Offset :=
              Stream_Element_Offset (Total_Len - 8);
         begin
            for B in 0 .. 7 loop
               Msg (Len_Pos + Stream_Element_Offset (B)) :=
                 Stream_Element
                   (Shift_Right (Msg_Len_Bits,
                      (7 - B) * 8) and 16#FF#);
            end loop;
         end;

         --  Process each 512-bit (64-byte) block.
         declare
            Num_Blocks : constant Natural := Total_Len / 64;
         begin
            for Blk in 0 .. Num_Blocks - 1 loop
               declare
                  W    : array (0 .. 63) of Unsigned_32 := (others => 0);
                  Base : constant Stream_Element_Offset :=
                    Stream_Element_Offset (Blk * 64);
                  A, B, C, D, E, F, G, Hh : Unsigned_32;
                  T1, T2 : Unsigned_32;
               begin
                  for T in 0 .. 15 loop
                     declare
                        Off : constant Stream_Element_Offset :=
                          Base + Stream_Element_Offset (T * 4);
                     begin
                        W (T) :=
                          Shift_Left (Unsigned_32 (Msg (Off)), 24) or
                          Shift_Left (Unsigned_32 (Msg (Off + 1)), 16) or
                          Shift_Left (Unsigned_32 (Msg (Off + 2)), 8) or
                          Unsigned_32 (Msg (Off + 3));
                     end;
                  end loop;

                  for T in 16 .. 63 loop
                     W (T) :=
                       Small_Sigma1 (W (T - 2)) + W (T - 7) +
                       Small_Sigma0 (W (T - 15)) + W (T - 16);
                  end loop;

                  A := H (0); B := H (1); C := H (2); D := H (3);
                  E := H (4); F := H (5); G := H (6); Hh := H (7);

                  for T in 0 .. 63 loop
                     T1 := Hh + Big_Sigma1 (E) + Ch (E, F, G) + K (T) + W (T);
                     T2 := Big_Sigma0 (A) + Maj (A, B, C);
                     Hh := G;
                     G  := F;
                     F  := E;
                     E  := D + T1;
                     D  := C;
                     C  := B;
                     B  := A;
                     A  := T1 + T2;
                  end loop;

                  H (0) := H (0) + A;
                  H (1) := H (1) + B;
                  H (2) := H (2) + C;
                  H (3) := H (3) + D;
                  H (4) := H (4) + E;
                  H (5) := H (5) + F;
                  H (6) := H (6) + G;
                  H (7) := H (7) + Hh;
               end;
            end loop;
         end;

         declare
            Result : Digest_Type;
         begin
            for I in 0 .. 7 loop
               Result (I * 4)     := Unsigned_8 (Shift_Right (H (I), 24) and 16#FF#);
               Result (I * 4 + 1) := Unsigned_8 (Shift_Right (H (I), 16) and 16#FF#);
               Result (I * 4 + 2) := Unsigned_8 (Shift_Right (H (I), 8) and 16#FF#);
               Result (I * 4 + 3) := Unsigned_8 (H (I) and 16#FF#);
            end loop;
            return Result;
         end;
      end;
   end Hash;

   function Hash (Data : String) return Digest_Type is
      Buf : Stream_Element_Array (0 .. Stream_Element_Offset (Data'Length - 1));
   begin
      for I in Data'Range loop
         Buf (Stream_Element_Offset (I - Data'First)) :=
           Stream_Element (Character'Pos (Data (I)) mod 256);
      end loop;
      return Hash (Buf);
   end Hash;

   ------------
   -- To_Hex --
   ------------

   function To_Hex (D : Digest_Type) return Hex_Digest_String is
      Hex_Chars : constant String := "0123456789abcdef";
      Result    : Hex_Digest_String;
   begin
      for I in Digest_Index loop
         Result (I * 2 + 1) :=
           Hex_Chars (Integer (Shift_Right (D (I), 4)) + 1);
         Result (I * 2 + 2) :=
           Hex_Chars (Integer (D (I) and 16#0F#) + 1);
      end loop;
      return Result;
   end To_Hex;

   --------------
   -- Hash_Hex --
   --------------

   function Hash_Hex (Data : String) return Hex_Digest_String is
     (To_Hex (Hash (Data)));

end SHA256_Core;

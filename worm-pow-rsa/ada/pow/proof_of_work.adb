--  Proof_Of_Work body.
--  UNVERIFIED: has not been compiled or run.

package body Proof_Of_Work with SPARK_Mode is

   --  Trim an Integer to its minimal decimal ASCII representation
   --  (no leading '+', no leading zeros beyond a single "0").
   function Trim_Image (N : Natural) return String is
      S : constant String := Natural'Image (N);
   begin
      --  Natural'Image never has a leading '-' but does have a leading
      --  space for the sign slot; strip it.
      return S (S'First + 1 .. S'Last);
   end Trim_Image;

   -------------------
   -- Header_Digest --
   -------------------

   procedure Header_Digest
     (Header  : PoW_Header;
      Digest  : out Hash_Hex;
      Success : out Boolean)
   is
      use Canonical_JSON;

      Seq_Str   : constant String := Trim_Image (Header.Sequence);
      Ts_Str    : constant String := Trim_Image (Header.Timestamp);
      Nonce_Str : constant String := Trim_Image (Header.Nonce);

      --  Canonical field order: strict ascending byte-wise key order.
      --  Keys: nonce, payload_hash, prev_hash, sequence, timestamp
      Fields : constant Field_List (1 .. 5) :=
        (1 => Make_Integer_Field ("nonce", Nonce_Str),
         2 => Make_String_Field ("payload_hash", Header.Payload_Hash),
         3 => Make_String_Field ("prev_hash", Header.Prev_Hash),
         4 => Make_Integer_Field ("sequence", Seq_Str),
         5 => Make_Integer_Field ("timestamp", Ts_Str));

      Rendered : Output_String;
      Out_Len  : Natural;
      Render_Ok : Boolean;
   begin
      Digest := (others => '0');
      Success := False;

      Render (Fields, Rendered, Out_Len, Render_Ok);
      if not Render_Ok then
         return;
      end if;

      Digest := SHA256_Core.Hash_Hex (Rendered (1 .. Out_Len));
      Success := True;
   end Header_Digest;

   ----------------------
   -- Meets_Difficulty --
   ----------------------

   function Meets_Difficulty
     (Digest     : Hash_Hex;
      Difficulty : Difficulty_Level) return Boolean
   is
   begin
      if Difficulty = 0 then
         return True;
      end if;
      for I in 1 .. Difficulty loop
         if Digest (I) /= '0' then
            return False;
         end if;
      end loop;
      return True;
   end Meets_Difficulty;

   -----------------
   -- Find_Nonce --
   -----------------

   procedure Find_Nonce
     (Base_Header  : PoW_Header;
      Difficulty   : Difficulty_Level;
      Max_Nonce    : Natural := Default_Max_Nonce;
      Result       : out Search_Result;
      Found_Nonce  : out Natural;
      Found_Digest : out Hash_Hex)
   is
      Trial : PoW_Header := Base_Header;
      Digest : Hash_Hex;
      Digest_Ok : Boolean;
   begin
      Found_Nonce := 0;
      Found_Digest := (others => '0');

      for N in 0 .. Max_Nonce loop
         Trial.Nonce := N;
         Header_Digest (Trial, Digest, Digest_Ok);
         if not Digest_Ok then
            Result := Canonicalization_Failed;
            return;
         end if;

         if Meets_Difficulty (Digest, Difficulty) then
            Result := Found;
            Found_Nonce := N;
            Found_Digest := Digest;
            return;
         end if;
      end loop;

      Result := Exhausted;
   end Find_Nonce;

   -----------------
   -- Verify_PoW --
   -----------------

   function Verify_PoW
     (Header     : PoW_Header;
      Difficulty : Difficulty_Level) return Boolean
   is
      Digest    : Hash_Hex;
      Digest_Ok : Boolean;
   begin
      Header_Digest (Header, Digest, Digest_Ok);
      if not Digest_Ok then
         return False;  --  fail closed: cannot verify, so not verified
      end if;
      return Meets_Difficulty (Digest, Difficulty);
   end Verify_PoW;

end Proof_Of_Work;

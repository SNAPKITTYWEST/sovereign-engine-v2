--  Canonical_JSON body.
--  UNVERIFIED: has not been compiled or run.

package body Canonical_JSON with SPARK_Mode is

   function Make_String_Field (Key, Value : String) return Field is
      F : Field;
   begin
      F.Key (1 .. Key'Length) := Key;
      F.Key_Len := Key'Length;
      F.Value (1 .. Value'Length) := Value;
      F.Value_Len := Value'Length;
      F.Kind := String_Value;
      return F;
   end Make_String_Field;

   function Make_Integer_Field (Key : String; Value : String) return Field is
      F : Field;
   begin
      F.Key (1 .. Key'Length) := Key;
      F.Key_Len := Key'Length;
      F.Value (1 .. Value'Length) := Value;
      F.Value_Len := Value'Length;
      F.Kind := Integer_Value;
      return F;
   end Make_Integer_Field;

   --  Byte-wise ascending compare of two keys (as stored, trimmed to
   --  their logical length).
   function Key_Less (A : Field; B : Field) return Boolean is
      Min_Len : constant Natural :=
        Natural'Min (A.Key_Len, B.Key_Len);
   begin
      for I in 1 .. Min_Len loop
         if A.Key (I) /= B.Key (I) then
            return A.Key (I) < B.Key (I);
         end if;
      end loop;
      return A.Key_Len < B.Key_Len;
   end Key_Less;

   --  Append Src (logical length Src_Len) to Buf at position Pos,
   --  advancing Pos. Fails closed (returns False) on overflow.
   procedure Append
     (Buf     : in out Output_String;
      Pos     : in out Natural;
      Src     : String;
      Src_Len : Natural;
      Ok      : in out Boolean)
   is
   begin
      if not Ok then
         return;
      end if;
      if Pos + Src_Len > Max_Output_Len then
         Ok := False;
         return;
      end if;
      Buf (Pos + 1 .. Pos + Src_Len) := Src (Src'First .. Src'First + Src_Len - 1);
      Pos := Pos + Src_Len;
   end Append;

   procedure Append_Char
     (Buf : in out Output_String;
      Pos : in out Natural;
      C   : Character;
      Ok  : in out Boolean)
   is
   begin
      if not Ok then
         return;
      end if;
      if Pos + 1 > Max_Output_Len then
         Ok := False;
         return;
      end if;
      Pos := Pos + 1;
      Buf (Pos) := C;
   end Append_Char;

   --  Escape a string value per RFC 8785 / JSON string rules: escape
   --  '"', '\', and C0 control characters (0x00-0x1F) using the short
   --  escapes where defined (\n \t \r \b \f \") and \u00XX otherwise.
   --  Fails closed on any byte >= 0x80 that is not straightforward
   --  ASCII, to avoid guessing at UTF-8 validity here — callers dealing
   --  in non-ASCII payload text should pre-validate encoding upstream;
   --  this canonicalizer refuses rather than mis-encodes.
   procedure Escape_Into
     (Buf     : in out Output_String;
      Pos     : in out Natural;
      Src     : String;
      Src_Len : Natural;
      Ok      : in out Boolean)
   is
      Hex_Chars : constant String := "0123456789abcdef";
   begin
      Append_Char (Buf, Pos, '"', Ok);
      for I in 1 .. Src_Len loop
         declare
            C  : constant Character := Src (Src'First + I - 1);
            Cp : constant Natural := Character'Pos (C);
         begin
            case C is
               when '"'  => Append (Buf, Pos, "\""", 2, Ok);
               when '\'  => Append (Buf, Pos, "\\", 2, Ok);
               when ASCII.LF => Append (Buf, Pos, "\n", 2, Ok);
               when ASCII.CR => Append (Buf, Pos, "\r", 2, Ok);
               when ASCII.HT => Append (Buf, Pos, "\t", 2, Ok);
               when others =>
                  if Cp < 16#20# then
                     declare
                        Esc : String (1 .. 6) := "\u0000";
                     begin
                        Esc (5) := Hex_Chars (Cp / 16 + 1);
                        Esc (6) := Hex_Chars (Cp mod 16 + 1);
                        Append (Buf, Pos, Esc, 6, Ok);
                     end;
                  elsif Cp <= 16#7E# then
                     Append_Char (Buf, Pos, C, Ok);
                  else
                     --  Non-ASCII byte: refuse rather than guess at
                     --  intended UTF-8 codepoint boundaries.
                     Ok := False;
                  end if;
            end case;
         end;
         exit when not Ok;
      end loop;
      Append_Char (Buf, Pos, '"', Ok);
   end Escape_Into;

   ------------
   -- Render --
   ------------

   procedure Render
     (Fields  : Field_List;
      Output  : out Output_String;
      Out_Len : out Natural;
      Success : out Boolean)
   is
      Pos : Natural := 0;
      Ok  : Boolean := True;
   begin
      Output := (others => ' ');
      Out_Len := 0;
      Success := False;

      if Fields'Length = 0 then
         --  An empty record is not a meaningful canonical form for the
         --  fixed shapes this ledger uses; refuse rather than emit "{}"
         --  silently for what is likely a construction bug upstream.
         return;
      end if;

      --  Verify strict ascending key order (fail closed if violated —
      --  never silently re-sort, since that would mask an upstream bug).
      for I in Fields'First .. Fields'Last - 1 loop
         if not Key_Less (Fields (I), Fields (I + 1)) then
            return;
         end if;
      end loop;

      Append_Char (Output, Pos, '{', Ok);

      for I in Fields'Range loop
         if I /= Fields'First then
            Append_Char (Output, Pos, ',', Ok);
         end if;

         Escape_Into (Output, Pos, Fields (I).Key, Fields (I).Key_Len, Ok);
         Append_Char (Output, Pos, ':', Ok);

         case Fields (I).Kind is
            when String_Value =>
               Escape_Into
                 (Output, Pos, Fields (I).Value, Fields (I).Value_Len, Ok);
            when Integer_Value | Raw_Literal =>
               Append
                 (Output, Pos, Fields (I).Value, Fields (I).Value_Len, Ok);
         end case;

         exit when not Ok;
      end loop;

      Append_Char (Output, Pos, '}', Ok);

      if Ok then
         Out_Len := Pos;
         Success := True;
      end if;
   end Render;

end Canonical_JSON;

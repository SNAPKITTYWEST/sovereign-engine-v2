--  WORM_Store body.
--  UNVERIFIED: has not been compiled or run; the Post-condition on
--  Append has not been discharged by gnatprove on this machine (no
--  toolchain installed here) — treat as documentation-grade until
--  proven.

package body WORM_Store with SPARK_Mode is

   ------------
   -- Append --
   ------------

   procedure Append
     (S      : in out Store;
      Item   : String;
      Result : out Append_Result)
   is
   begin
      if S.Count >= Max_Records then
         Result := Store_Full;
         return;
      end if;

      if Item'Length > Max_Record_Len then
         Result := Record_Too_Large;
         return;
      end if;

      declare
         New_Index : constant Record_Index := S.Count + 1;
         New_Rec   : Stored_Record;
      begin
         New_Rec.Data (1 .. Item'Length) := Item;
         New_Rec.Len := Item'Length;
         S.Records (New_Index) := New_Rec;
         S.Count := New_Index;
      end;

      Result := Appended;
   end Append;

   ---------
   -- Get --
   ---------

   function Get
     (S : Store; Index : Record_Index) return Stored_Record
   is
   begin
      return S.Records (Index);
   end Get;

end WORM_Store;

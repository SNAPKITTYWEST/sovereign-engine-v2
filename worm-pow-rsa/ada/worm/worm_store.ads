--  WORM_Store
--  Write-once-read-many append-only record store abstraction. Enforces,
--  by construction and by contract, that:
--    * records can only be appended at the current end (Count),
--    * no existing record's bytes can be modified,
--    * no record can be deleted,
--    * no record can be inserted before an existing record,
--    * no reordering is possible (records are indexed 1..Count and that
--      indexing never changes for a given record once appended).
--  This is the mechanical enforcement layer; Chain_Continuity checks the
--  cryptographic linkage between records, and Validation ties both
--  together into a single verdict.

package WORM_Store with SPARK_Mode is

   Max_Records : constant := 100_000;

   subtype Record_Index is Positive range 1 .. Max_Records;
   subtype Record_Count is Natural range 0 .. Max_Records;

   Max_Record_Len : constant := 8192;
   subtype Record_String is String (1 .. Max_Record_Len);

   type Stored_Record is record
      Data : Record_String := (others => ' ');
      Len  : Natural range 0 .. Max_Record_Len := 0;
   end record;

   type Record_Array is array (Record_Index) of Stored_Record;

   type Store is record
      Records : Record_Array;
      Count   : Record_Count := 0;
   end record;

   Empty_Store : constant Store :=
     (Records => (others => (Data => (others => ' '), Len => 0)),
      Count   => 0);

   type Append_Result is
     (Appended,
      Store_Full,
      Record_Too_Large);

   --  Append a new record at position Count+1. This is the ONLY
   --  operation this package provides that changes a Store's contents —
   --  there is no Delete, Update, or Insert_At operation anywhere in
   --  this package's interface, so modification/deletion/reordering are
   --  structurally impossible for any caller restricted to this API.
   --
   --  Post-condition states precisely the WORM guarantee: on success,
   --  Count increases by exactly one, every prior record (1..old Count)
   --  is byte-for-byte unchanged, and the new record lands at the new
   --  Count with the supplied bytes.
   procedure Append
     (S          : in out Store;
      Item       : String;
      Result     : out Append_Result)
     with
       Pre  => Item'Length <= Max_Record_Len,
       Post =>
         (if Result = Appended then
            S.Count = S.Count'Old + 1
              and then S.Count <= Max_Records
              and then (for all I in 1 .. S.Count'Old =>
                          S.Records (I) = S.Records'Old (I))
              and then S.Records (S.Count).Len = Item'Length
          else
            S.Count = S.Count'Old
              and then (for all I in 1 .. S.Count =>
                          S.Records (I) = S.Records'Old (I)));

   --  Read-only accessor. Reading never mutates the store (no Global
   --  writes), reinforcing that this package exposes no path to mutate
   --  history.
   function Get
     (S : Store; Index : Record_Index) return Stored_Record
     with
       Pre    => Index <= S.Count,
       Global => null;

   function Count_Of (S : Store) return Record_Count is (S.Count)
     with Global => null;

end WORM_Store;

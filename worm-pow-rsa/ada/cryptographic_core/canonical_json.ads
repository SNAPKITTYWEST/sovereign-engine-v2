--  Canonical_JSON
--  Minimal RFC 8785 (JCS)-style canonicalization for the fixed record
--  shapes used by this ledger (PoW headers and chain records). This is
--  NOT a general JSON canonicalizer — it does not parse arbitrary JSON.
--  Callers assemble a Field_List describing an already-known record
--  shape, and this package renders it in canonical form: sorted keys
--  (callers must supply Field_List already sorted — Is_Sorted checks and
--  fails closed if not), no insignificant whitespace, and consistent
--  escaping. Fail-closed: any field whose value cannot be rendered
--  unambiguously (e.g. containing raw control characters, unbalanced
--  data) results in Success = False rather than a best-effort guess.

package Canonical_JSON with SPARK_Mode is

   Max_Fields : constant := 16;
   Max_Key_Len : constant := 64;
   Max_Value_Len : constant := 4096;

   subtype Key_String is String (1 .. Max_Key_Len);
   subtype Value_String is String (1 .. Max_Value_Len);

   type Value_Kind is (String_Value, Integer_Value, Raw_Literal);
   --  String_Value : rendered as a quoted, escaped JSON string.
   --  Integer_Value: the Value field holds a decimal ASCII integer,
   --                 rendered unquoted verbatim (caller guarantees it is
   --                 a valid JSON number, e.g. from Integer'Image trimmed).
   --  Raw_Literal  : rendered exactly as given (e.g. "true", "null") —
   --                 use only for known-safe fixed literals.

   type Field is record
      Key       : Key_String := (others => ' ');
      Key_Len   : Natural range 0 .. Max_Key_Len := 0;
      Value     : Value_String := (others => ' ');
      Value_Len : Natural range 0 .. Max_Value_Len := 0;
      Kind      : Value_Kind := String_Value;
   end record;

   type Field_Index is range 1 .. Max_Fields;
   type Field_List is array (Field_Index range <>) of Field;

   --  Result buffer sizing: generous fixed bound for the fixed record
   --  shapes this ledger uses (PoW headers, chain records are small).
   Max_Output_Len : constant := 8192;
   subtype Output_String is String (1 .. Max_Output_Len);

   --  Render Fields into canonical JSON object form: {"k1":"v1","k2":v2}.
   --  Fields must already be supplied in strict ascending key order
   --  (byte-wise); this is checked and enforced (fail closed) rather
   --  than sorted internally, so callers cannot accidentally rely on an
   --  implicit sort that masks a construction bug upstream.
   procedure Render
     (Fields    : Field_List;
      Output    : out Output_String;
      Out_Len   : out Natural;
      Success   : out Boolean);

   --  Helper constructors for Field values.
   function Make_String_Field (Key, Value : String) return Field
     with Pre => Key'Length <= Max_Key_Len and then Value'Length <= Max_Value_Len;

   function Make_Integer_Field (Key : String; Value : String) return Field
     with Pre => Key'Length <= Max_Key_Len and then Value'Length <= Max_Value_Len;

end Canonical_JSON;

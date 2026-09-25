--  SHA256_Core
--  Full from-scratch implementation of SHA-256 per FIPS 180-4.
--  Fail-closed: this package never guesses; malformed input lengths that
--  cannot occur (Ada strings are always well-formed byte sequences) are
--  handled by construction, not by exception.

with Interfaces; use Interfaces;
with Ada.Streams; use Ada.Streams;

package SHA256_Core with SPARK_Mode is

   Digest_Bytes : constant := 32;

   subtype Digest_Index is Natural range 0 .. Digest_Bytes - 1;
   type Digest_Type is array (Digest_Index) of Unsigned_8;

   --  A digest rendered as lowercase hex, 64 characters.
   subtype Hex_Digest_String is String (1 .. 64);

   function To_Hex (D : Digest_Type) return Hex_Digest_String
     with Post => To_Hex'Result'Length = 64;

   --  Compute SHA-256 over an arbitrary byte buffer.
   function Hash (Data : Stream_Element_Array) return Digest_Type;

   --  Convenience: compute SHA-256 over a String, treating each character
   --  as a single byte (the canonical JSON forms used elsewhere in this
   --  system are restricted to the printable ASCII / UTF-8 byte range).
   function Hash (Data : String) return Digest_Type;

   function Hash_Hex (Data : String) return Hex_Digest_String;

end SHA256_Core;

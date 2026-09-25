--  Cryptographic_Core body.
--  UNVERIFIED: has not been compiled or run.

package body Cryptographic_Core with SPARK_Mode is

   -------------------
   -- Verify_Record --
   -------------------

   function Verify_Record
     (Key       : RSA_Verify.Public_Key;
      Digest    : SHA256_Core.Digest_Type;
      Signature : Big_Num.Unsigned_8_Array;
      Prev      : Chain_Continuity.Record_Header;
      Current   : Ledger_Validator.Record_Input) return Overall_Status
   is
      Sig_Result : constant RSA_Verify.Verify_Result :=
        RSA_Verify.Verify (Key, Digest, Signature);
   begin
      case Sig_Result is
         when RSA_Verify.Valid =>
            null;  --  proceed to chain validation below
         when RSA_Verify.Invalid_Signature =>
            return Signature_Invalid;
         when RSA_Verify.Malformed_Key
            | RSA_Verify.Malformed_Signature
            | RSA_Verify.Malformed_Padding
            | RSA_Verify.Unsupported_Key_Size =>
            return Signature_Malformed;
      end case;

      declare
         Chain_Verdict : constant Ledger_Validator.Verdict :=
           Ledger_Validator.Validate (Prev, Current);
      begin
         if Chain_Verdict.Valid then
            return Verified;
         else
            return Chain_Invalid;
         end if;
      end;
   end Verify_Record;

end Cryptographic_Core;

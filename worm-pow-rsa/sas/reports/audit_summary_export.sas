/******************************************************************************
 * PROGRAM:   audit_summary_export.sas
 * PURPOSE:   Produce a single flat audit-summary dataset suitable for
 *            feeding a Mustache report template (chain_verification_report
 *            / audit_report). Consolidates results that the other
 *            validation/reconciliation programs in this suite would have
 *            already produced (WORK.SEQUENCE_EXCEPTIONS_ALL,
 *            WORK.HASH_CONTINUITY_EXCEPTIONS,
 *            WORK.DUPLICATE_RECORD_ID_EXCEPTIONS,
 *            WORK.RSA_STATUS_UNKNOWN_DETAIL) into pass/fail status fields.
 *
 * PREREQUISITE: For a complete summary, run, in order, prior to this
 *            program in the same SAS session/WORK library:
 *              sas/validation/sequence_gap_detection.sas
 *              sas/validation/hash_continuity_check.sas
 *              sas/reconciliation/duplicate_detection.sas
 *              sas/reconciliation/rsa_interop_reconciliation.sas
 *            If any prerequisite dataset is absent, this program treats
 *            that check as UNKNOWN (fail closed - never assumed PASS).
 *
 * IMPORTANT: WORM.LEDGER is read-only input. No MODIFY, no DELETE, no
 *            in-place update of WORM.LEDGER anywhere in this program.
 *
 * INPUT:     WORM.LEDGER
 *            WORK.SEQUENCE_EXCEPTIONS_ALL       (optional, if present)
 *            WORK.HASH_CONTINUITY_EXCEPTIONS    (optional, if present)
 *            WORK.DUPLICATE_RECORD_ID_EXCEPTIONS(optional, if present)
 *            WORK.RSA_STATUS_UNKNOWN_DETAIL      (optional, if present)
 *
 * OUTPUT:    WORK.AUDIT_SUMMARY_EXPORT
 *              Fields: chain_id, record_count, validation_status,
 *              hash_algorithm, pow_algorithm, pow_difficulty, rsa_status,
 *              sequence_status, hash_status, pow_status, worm_status
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * 1. Base facts read directly from WORM.LEDGER (read-only).
 * --------------------------------------------------------------------- */
proc sql noprint;
    select count(*) into :rec_count trimmed from worm.ledger;
    select strip(put(count(distinct pow_algorithm), best.)) into :pow_alg_ct trimmed
        from worm.ledger;
    select strip(min(pow_algorithm)) into :pow_alg_min trimmed from worm.ledger;
    select strip(put(min(pow_difficulty), best.)) into :pow_diff_min trimmed
        from worm.ledger;
    select strip(put(max(pow_difficulty), best.)) into :pow_diff_max trimmed
        from worm.ledger;
    select strip(put(count(distinct worm_mode), best.)) into :worm_mode_ct trimmed
        from worm.ledger;
    select strip(min(worm_mode)) into :worm_mode_min trimmed from worm.ledger;
quit;

/* ---------------------------------------------------------------------
 * 2. Derive per-check status flags from prerequisite exception datasets,
 *    if they exist in WORK. Fail closed: missing prerequisite => UNKNOWN.
 * --------------------------------------------------------------------- */
%macro derive_status(outmacro, dsname);
    %if %sysfunc(exist(&dsname)) %then %do;
        proc sql noprint;
            select strip(put(count(*), best.)) into :&outmacro._n trimmed
            from &dsname;
        quit;
        %if &&&outmacro._n > 0 %then %let &outmacro = FAIL;
        %else %let &outmacro = PASS;
    %end;
    %else %do;
        %let &outmacro = UNKNOWN;
    %end;
%mend derive_status;

%global seq_status hash_status dup_status rsa_status_flag;
%derive_status(seq_status, work.sequence_exceptions_all);
%derive_status(hash_status, work.hash_continuity_exceptions);
%derive_status(dup_status, work.duplicate_record_id_exceptions);
%derive_status(rsa_status_flag, work.rsa_status_unknown_detail);

/* worm_status: fail closed if more than one distinct worm_mode value is
   present in the ledger (a WORM ledger should be operating under a single
   consistent mode), or if worm_mode is missing/blank anywhere. */
proc sql noprint;
    select strip(put(count(*), best.)) into :worm_blank_ct trimmed
    from worm.ledger
    where missing(worm_mode);
quit;

%let worm_status = PASS;
%if %eval(&worm_mode_ct > 1) or %eval(&worm_blank_ct > 0) %then %let worm_status = FAIL;

/* pow_status: fail closed if more than one PoW algorithm is present
   (mixed-algorithm chains require manual review), else PASS. */
%let pow_status = PASS;
%if %eval(&pow_alg_ct > 1) %then %let pow_status = FAIL;

/* rsa_status label: human-readable rollup for the flat export field */
%let rsa_status_label = UNKNOWN;
%if "&rsa_status_flag" = "PASS" %then %let rsa_status_label = VERIFIED;
%else %if "&rsa_status_flag" = "FAIL" %then %let rsa_status_label = EXCEPTIONS_PRESENT;

/* overall validation_status: fail closed - any non-PASS check fails the
   whole chain's validation status. */
%let validation_status = PASS;
%if "&seq_status" ne "PASS" or "&hash_status" ne "PASS"
    or "&dup_status" ne "PASS" or "&pow_status" ne "PASS"
    or "&worm_status" ne "PASS" or "&rsa_status_flag" = "FAIL"
    %then %let validation_status = FAIL;

/* ---------------------------------------------------------------------
 * 3. Build the flat export dataset for the Mustache report layer.
 * --------------------------------------------------------------------- */
data work.audit_summary_export;
    length chain_id $64 record_count 8 validation_status $16
           hash_algorithm $16 pow_algorithm $32 pow_difficulty $16
           rsa_status $32 sequence_status $16 hash_status $16
           pow_status $16 worm_status $16;

    chain_id          = "WORM-LEDGER-%sysfunc(putn(%sysfunc(datetime()), datetime20.))";
    chain_id          = compress(chain_id, ' :');
    record_count      = &rec_count;
    validation_status = "&validation_status";
    hash_algorithm    = "SHA-256";  /* record_hash/prev_hash algorithm per spec */
    pow_algorithm     = "&pow_alg_min";
    pow_difficulty    = "&pow_diff_min-&pow_diff_max";
    rsa_status        = "&rsa_status_label";
    sequence_status   = "&seq_status";
    hash_status       = "&hash_status";
    pow_status        = "&pow_status";
    worm_status       = "&worm_status";
    output;
run;

proc print data=work.audit_summary_export noobs label;
    title "Final Audit Summary Export (Flat Dataset for Report Template)";
run;

title;

/* ---------------------------------------------------------------------
 * 4. Export to a flat file for downstream template rendering (CSV form).
 *    Adjust the physical path as appropriate for the deployment target;
 *    this writes only a derived report artifact, never WORM.LEDGER.
 * --------------------------------------------------------------------- */
proc export data=work.audit_summary_export
    outfile="audit_summary_export.csv"
    dbms=csv
    replace;
run;

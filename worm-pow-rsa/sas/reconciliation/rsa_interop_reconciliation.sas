/******************************************************************************
 * PROGRAM:   rsa_interop_reconciliation.sas
 * PURPOSE:   Read-only reconciliation of RSA interoperability status
 *            counts across the WORM ledger (verified / not_verified /
 *            unknown), via PROC FREQ.
 *
 * SCOPE / LIMITATION: This program tabulates the rsa_verified field as
 *            already populated in WORM.LEDGER. It does NOT perform RSA
 *            signature verification itself - that is the responsibility
 *            of the Ada/SPARK cryptographic verification layer. SAS
 *            only counts and cross-checks the recorded status values.
 *
 * IMPORTANT: WORM.LEDGER is read-only input. No MODIFY, no DELETE, no
 *            in-place update of WORM.LEDGER anywhere in this program.
 *
 * INPUT:     WORM.LEDGER
 * OUTPUT:    WORK.RSA_STATUS_FREQ           (PROC FREQ output dataset)
 *            WORK.RSA_STATUS_UNKNOWN_DETAIL (rows needing investigation)
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * Normalize rsa_verified into a fixed set of expected categories for
 * cross-check purposes only (WORK copy; source untouched). Any value
 * outside Y/N/UNKNOWN is itself flagged as an exception rather than
 * silently bucketed.
 * --------------------------------------------------------------------- */
data work.rsa_status_check (keep=record_id sequence rsa_verified rsa_status_category);
    length rsa_status_category $16;
    set worm.ledger(keep=record_id sequence rsa_verified);

    select (upcase(strip(rsa_verified)));
        when ('Y')       rsa_status_category = 'VERIFIED';
        when ('N')       rsa_status_category = 'NOT_VERIFIED';
        when ('UNKNOWN') rsa_status_category = 'UNKNOWN';
        otherwise        rsa_status_category = 'INVALID_VALUE';
    end;
run;

/* ---------------------------------------------------------------------
 * PROC FREQ cross-check of RSA interoperability status counts.
 * --------------------------------------------------------------------- */
proc freq data=work.rsa_status_check;
    tables rsa_status_category / missing out=work.rsa_status_freq;
    title "RSA Interoperability Status Cross-Check (Verified / Not Verified / Unknown)";
run;

/* ---------------------------------------------------------------------
 * Detail listing of any UNKNOWN or INVALID_VALUE rows for follow-up -
 * fail closed rather than treating unknown/invalid as benign.
 * --------------------------------------------------------------------- */
data work.rsa_status_unknown_detail;
    set work.rsa_status_check;
    where rsa_status_category in ('UNKNOWN', 'INVALID_VALUE');
run;

proc sort data=work.rsa_status_unknown_detail;
    by sequence;
run;

proc print data=work.rsa_status_unknown_detail noobs label;
    title "RSA Interoperability Exceptions: UNKNOWN or Invalid rsa_verified Values";
run;

title;

/******************************************************************************
 * PROGRAM:   hash_continuity_check.sas
 * PURPOSE:   Read-only chain-continuity check. Verifies that
 *            prev_hash[n] = record_hash[n-1] for records sorted by
 *            sequence, using the LAG function for the lagged comparison.
 *
 * SCOPE / LIMITATION: This is a STRING EQUALITY check only. SAS does not
 *            recompute SHA-256 (or any other digest) here; it does not
 *            validate that record_hash or pow_hash are themselves correct
 *            hashes of their respective payloads. Cryptographic
 *            verification of hash correctness is the responsibility of
 *            the Ada/SPARK layer. This program only checks that the
 *            claimed prev_hash on record n textually matches the claimed
 *            record_hash on record n-1, i.e. chain linkage as recorded.
 *
 * IMPORTANT: WORM.LEDGER is read-only input (SET only). No MODIFY, no
 *            DELETE, no in-place update of WORM.LEDGER anywhere.
 *
 * INPUT:     WORM.LEDGER
 * OUTPUT:    WORK.HASH_SORTED                  (sorted working copy)
 *            WORK.HASH_CONTINUITY_EXCEPTIONS   (discontinuities flagged)
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * 1. Copy WORM.LEDGER into a WORK-only sorted dataset.
 * --------------------------------------------------------------------- */
proc sort data=worm.ledger(keep=sequence record_id prev_hash record_hash)
          out=work.hash_sorted;
    by sequence;
run;

/* ---------------------------------------------------------------------
 * 2. Lagged string comparison: prev_hash[n] must equal record_hash[n-1].
 *    LAG() returns the value of record_hash from the previous execution
 *    of the DATA step (i.e., the previous observation in sequence order).
 *    First record in the chain has no predecessor and is reported
 *    separately (informational), not flagged as a discontinuity, unless
 *    it has a non-missing prev_hash (which would itself be suspicious
 *    and is flagged).
 * --------------------------------------------------------------------- */
data work.hash_continuity_exceptions
        (keep=sequence record_id prev_hash expected_prev_hash
              exception_type exception_desc);

    length prior_record_hash $64 exception_type $32 exception_desc $200;
    set work.hash_sorted;

    /* LAG must be called unconditionally, every iteration, to keep the
       internal queue correctly aligned with the observation stream. */
    prior_record_hash = lag(record_hash);

    if _n_ = 1 then do;
        /* First record: no predecessor exists in this dataset. A
           non-missing prev_hash here cannot be validated against this
           dataset alone (it may legitimately reference a prior batch /
           genesis anchor) - flag as informational for manual review. */
        if not missing(prev_hash) then do;
            exception_type = 'GENESIS_PREV_HASH_UNVERIFIED';
            exception_desc = 'First record in sorted set has a non-missing '
                              || 'prev_hash; cannot verify against this '
                              || 'dataset - review against prior batch/anchor.';
            expected_prev_hash = '';
            output;
        end;
    end;
    else do;
        if prev_hash ne prior_record_hash then do;
            exception_type = 'HASH_DISCONTINUITY';
            exception_desc = 'prev_hash does not match record_hash of prior '
                              || 'record in sequence order (string compare only).';
            expected_prev_hash = prior_record_hash;
            output;
        end;
    end;
run;

proc sort data=work.hash_continuity_exceptions;
    by sequence;
run;

proc print data=work.hash_continuity_exceptions noobs label;
    title "Hash Continuity Exceptions (String Comparison Only - Not a SHA-256 Recompute)";
run;

title;

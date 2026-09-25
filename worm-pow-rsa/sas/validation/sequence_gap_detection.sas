/******************************************************************************
 * PROGRAM:   sequence_gap_detection.sas
 * PURPOSE:   Read-only validation of sequence continuity across the WORM
 *            ledger. Sorts by sequence, then flags:
 *              - any gap where sequence[n] != sequence[n-1] + 1
 *              - any duplicate sequence number
 *            Exceptions are written to an explicit output dataset. This
 *            program fails closed: any anomaly is flagged, never silently
 *            dropped or corrected in place.
 *
 * IMPORTANT: WORM.LEDGER is read-only input (SET only). No MODIFY, no
 *            DELETE, no in-place update of WORM.LEDGER anywhere.
 *
 * INPUT:     WORM.LEDGER
 * OUTPUT:    WORK.SEQ_SORTED               (sorted working copy, WORK only)
 *            WORK.SEQUENCE_GAP_EXCEPTIONS  (gap exceptions)
 *            WORK.SEQUENCE_DUP_EXCEPTIONS  (duplicate sequence exceptions)
 *            WORK.SEQUENCE_EXCEPTIONS_ALL  (combined exception dataset)
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * 1. Copy WORM.LEDGER into a WORK-only sorted dataset. PROC SORT with
 *    OUT= never touches the source dataset.
 * --------------------------------------------------------------------- */
proc sort data=worm.ledger(keep=sequence record_id timestamp) out=work.seq_sorted;
    by sequence;
run;

/* ---------------------------------------------------------------------
 * 2. Gap and duplicate detection via LAG-style comparison across the
 *    sorted, read-only copy.
 * --------------------------------------------------------------------- */
data work.sequence_gap_exceptions (keep=sequence prev_sequence record_id
                                        timestamp exception_type exception_desc)
     work.sequence_dup_exceptions (keep=sequence record_id timestamp
                                        exception_type exception_desc);

    set work.seq_sorted;
    by sequence;

    retain prev_sequence;
    length exception_type $32 exception_desc $200;

    /* Duplicate sequence: current key equals previous observation's key */
    if not first.sequence then do;
        exception_type = 'DUPLICATE_SEQUENCE';
        exception_desc = catx(' ', 'Duplicate sequence number detected:', sequence);
        output work.sequence_dup_exceptions;
    end;

    /* Gap detection: only evaluate once per distinct sequence value,
       comparing against the prior distinct sequence value */
    if first.sequence then do;
        if not missing(prev_sequence) and sequence ne prev_sequence + 1 then do;
            exception_type = 'SEQUENCE_GAP';
            exception_desc = catx(' ', 'Gap detected between sequence',
                                   prev_sequence, 'and', sequence);
            output work.sequence_gap_exceptions;
        end;
        prev_sequence = sequence;
    end;
run;

/* ---------------------------------------------------------------------
 * 3. Combine exception datasets into a single fail-closed exceptions view
 * --------------------------------------------------------------------- */
data work.sequence_exceptions_all;
    length exception_type $32 exception_desc $200;
    set work.sequence_gap_exceptions
        work.sequence_dup_exceptions;
run;

proc sort data=work.sequence_exceptions_all;
    by sequence exception_type;
run;

/* ---------------------------------------------------------------------
 * 4. Report exceptions (empty result set = clean chain; still printed
 *    explicitly so absence of exceptions is a visible, positive assertion
 *    rather than an assumption)
 * --------------------------------------------------------------------- */
proc print data=work.sequence_exceptions_all noobs label;
    title "Sequence Validation Exceptions (Gaps and Duplicates)";
run;

title;

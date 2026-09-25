/******************************************************************************
 * PROGRAM:   ledger_audit.sas
 * PURPOSE:   Read-only summary audit statistics over the WORM ledger.
 *            Computes total record count, distinct event_type counts,
 *            PoW difficulty distribution, min/max sequence, and chain span
 *            (first/last timestamp).
 *
 * IMPORTANT: This program NEVER modifies WORM.LEDGER. It only reads the
 *            dataset via SET / PROC steps. No MODIFY, no DELETE statements
 *            are permitted against WORM.LEDGER anywhere in this program.
 *
 * INPUT:     WORM.LEDGER
 * OUTPUT:    WORK.AUDIT_TOTAL_COUNT
 *            WORK.AUDIT_EVENT_TYPE_SUMMARY
 *            WORK.AUDIT_POW_DIFFICULTY_DIST
 *            WORK.AUDIT_SEQUENCE_RANGE
 *            WORK.AUDIT_CHAIN_SPAN
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * 1. Total record count (read-only pass over WORM.LEDGER)
 * --------------------------------------------------------------------- */
proc sql;
    create table work.audit_total_count as
    select count(*) as total_record_count
    from worm.ledger;
quit;

/* ---------------------------------------------------------------------
 * 2. Distinct event_type counts
 * --------------------------------------------------------------------- */
proc sql;
    create table work.audit_event_type_summary as
    select event_type,
           count(*) as event_count
    from worm.ledger
    group by event_type
    order by event_type;
quit;

/* ---------------------------------------------------------------------
 * 3. PoW difficulty distribution
 * --------------------------------------------------------------------- */
proc sql;
    create table work.audit_pow_difficulty_dist as
    select pow_algorithm,
           pow_difficulty,
           count(*) as record_count
    from worm.ledger
    group by pow_algorithm, pow_difficulty
    order by pow_algorithm, pow_difficulty;
quit;

/* ---------------------------------------------------------------------
 * 4. Min / max sequence number
 * --------------------------------------------------------------------- */
proc sql;
    create table work.audit_sequence_range as
    select min(sequence) as min_sequence,
           max(sequence) as max_sequence,
           (calculated max_sequence - calculated min_sequence + 1) as
                expected_record_count
    from worm.ledger;
quit;

/* ---------------------------------------------------------------------
 * 5. Chain span - first / last timestamp
 *    NOTE: timestamp is assumed char/datetime per spec; sorted as-is.
 *    If timestamp is a character ISO-8601 string, lexical min/max is
 *    valid. If it is a true SAS datetime numeric, min/max still works.
 * --------------------------------------------------------------------- */
proc sql;
    create table work.audit_chain_span as
    select min(timestamp) as first_timestamp,
           max(timestamp) as last_timestamp
    from worm.ledger;
quit;

/* ---------------------------------------------------------------------
 * 6. Consolidated audit log to the SAS log for human review
 * --------------------------------------------------------------------- */
proc print data=work.audit_total_count noobs label;
    title "Ledger Audit: Total Record Count";
run;

proc print data=work.audit_event_type_summary noobs label;
    title "Ledger Audit: Event Type Breakdown";
run;

proc print data=work.audit_pow_difficulty_dist noobs label;
    title "Ledger Audit: PoW Difficulty Distribution";
run;

proc print data=work.audit_sequence_range noobs label;
    title "Ledger Audit: Sequence Range";
run;

proc print data=work.audit_chain_span noobs label;
    title "Ledger Audit: Chain Span (First / Last Timestamp)";
run;

title;

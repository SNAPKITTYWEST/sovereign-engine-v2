/******************************************************************************
 * PROGRAM:   duplicate_detection.sas
 * PURPOSE:   Read-only reconciliation check for duplicate record_id values
 *            in the WORM ledger. A WORM ledger should never contain two
 *            records sharing the same record_id; any occurrence is a
 *            reconciliation exception requiring investigation.
 *
 * IMPORTANT: WORM.LEDGER is read-only input. No MODIFY, no DELETE, no
 *            in-place update of WORM.LEDGER anywhere in this program.
 *
 * INPUT:     WORM.LEDGER
 * OUTPUT:    WORK.DUPLICATE_RECORD_ID_EXCEPTIONS
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * Find duplicate record_id values via GROUP BY / HAVING COUNT(*) > 1.
 * This is a pure aggregate read against WORM.LEDGER; no rows in the
 * source dataset are altered.
 * --------------------------------------------------------------------- */
proc sql;
    create table work.duplicate_record_id_exceptions as
    select record_id,
           count(*) as occurrence_count,
           'DUPLICATE_RECORD_ID' as exception_type length=32
    from worm.ledger
    group by record_id
    having count(*) > 1
    order by occurrence_count desc, record_id;
quit;

/* ---------------------------------------------------------------------
 * Detail listing of every ledger row involved in a duplicate record_id,
 * to support manual investigation (fail closed: show the full context,
 * not just the aggregate count).
 * --------------------------------------------------------------------- */
proc sql;
    create table work.duplicate_record_id_detail as
    select l.record_id,
           l.sequence,
           l.timestamp,
           l.event_type,
           l.record_hash
    from worm.ledger as l
    where l.record_id in (select record_id from work.duplicate_record_id_exceptions)
    order by l.record_id, l.sequence;
quit;

proc print data=work.duplicate_record_id_exceptions noobs label;
    title "Reconciliation Exceptions: Duplicate record_id Values";
run;

proc print data=work.duplicate_record_id_detail noobs label;
    title "Reconciliation Detail: Ledger Rows With Duplicate record_id";
run;

title;

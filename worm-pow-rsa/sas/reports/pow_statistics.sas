/******************************************************************************
 * PROGRAM:   pow_statistics.sas
 * PURPOSE:   Read-only PoW search-cost statistics per difficulty level,
 *            using PROC MEANS and PROC UNIVARIATE on pow_nonce.
 *
 * SCOPE / LIMITATION: This program reports on the nonce values already
 *            recorded in WORM.LEDGER as a proxy for PoW search cost. It
 *            does not recompute or re-verify the proof-of-work itself.
 *
 * IMPORTANT: WORM.LEDGER is read-only input. No MODIFY, no DELETE, no
 *            in-place update of WORM.LEDGER anywhere in this program.
 *
 * INPUT:     WORM.LEDGER
 * OUTPUT:    WORK.POW_NONCE_MEANS_BY_DIFFICULTY  (PROC MEANS summary)
 *            WORK.POW_NONCE_UNIVARIATE_STATS      (PROC UNIVARIATE stats)
 *            WORK.POW_NONCE_EXTREME_OBS           (extreme observations)
 ******************************************************************************/

options nodate nonumber missing = 'UNKNOWN';

/* ---------------------------------------------------------------------
 * Read-only working extract (WORK copy only; WORM.LEDGER untouched).
 * --------------------------------------------------------------------- */
data work.pow_extract (keep=sequence pow_algorithm pow_difficulty pow_nonce);
    set worm.ledger(keep=sequence pow_algorithm pow_difficulty pow_nonce);
run;

proc sort data=work.pow_extract;
    by pow_algorithm pow_difficulty;
run;

/* ---------------------------------------------------------------------
 * PROC MEANS: search-cost statistics per PoW algorithm / difficulty
 * level - N, mean, std dev, min, max, and quartiles of pow_nonce.
 * --------------------------------------------------------------------- */
proc means data=work.pow_extract n mean std min max q1 median q3 maxdec=2;
    class pow_algorithm pow_difficulty;
    var pow_nonce;
    output out=work.pow_nonce_means_by_difficulty
        n=n_records mean=mean_nonce std=std_nonce
        min=min_nonce max=max_nonce
        q1=q1_nonce median=median_nonce q3=q3_nonce;
    title "PoW Search-Cost Statistics (Nonce) by Algorithm and Difficulty";
run;

/* ---------------------------------------------------------------------
 * PROC UNIVARIATE: detailed distribution statistics on pow_nonce for
 * each difficulty level, including extreme observations, to surface
 * potential outliers worth manual audit (not automatically flagged as
 * an integrity failure - this is descriptive, not a hard pass/fail).
 * --------------------------------------------------------------------- */
proc univariate data=work.pow_extract noprint;
    by pow_algorithm pow_difficulty;
    var pow_nonce;
    output out=work.pow_nonce_univariate_stats
        n=n mean=mean std=std var=variance
        min=min max=max range=range
        skewness=skewness kurtosis=kurtosis
        p1=p1 p5=p5 p95=p95 p99=p99;
run;

proc univariate data=work.pow_extract;
    by pow_algorithm pow_difficulty;
    var pow_nonce;
    output out=work.pow_nonce_extreme_obs_stats n=n;
    id sequence;
    title "PoW Nonce Distribution Detail and Extreme Observations";
run;

proc print data=work.pow_nonce_means_by_difficulty noobs label;
    title "PoW Search-Cost Summary (PROC MEANS Output)";
run;

proc print data=work.pow_nonce_univariate_stats noobs label;
    title "PoW Nonce Univariate Distribution Statistics";
run;

title;

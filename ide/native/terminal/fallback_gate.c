/*
 * Sovereign IDE — Terminal Fallback Gate
 *
 * Phase 2: Terminal user-control configuration.
 *
 * Problem: Agent can produce shell commands. If those commands execute
 * immediately in the terminal, the user loses control. This module
 * implements a FALLBACK MODE where:
 *
 *   1. Agent output is staged in a pending buffer (not sent to terminal)
 *   2. User sees the staged command in the terminal view (highlighted)
 *   3. Nothing executes until the user presses Enter (manual confirmation)
 *   4. Ctrl+K D routes text to terminal WITHOUT executing (populate only)
 *   5. Escape cancels the staged command entirely
 *
 * Modes:
 *   TERMINAL_MODE_DIRECT   — commands execute immediately (no gate)
 *   TERMINAL_MODE_FALLBACK — commands require manual Enter confirmation
 *   TERMINAL_MODE_PREVIEW  — commands shown read-only (copy only, no exec)
 *
 * The fallback gate sits between the bridge (agent responses) and
 * terminal_write(). It intercepts all agent-originated payloads.
 * User keystrokes bypass the gate entirely (direct to ConPTY).
 *
 * Security invariant: agent NEVER executes without user confirmation
 * when fallback mode is active. This is a hard gate, not advisory.
 */

#include "fallback_gate.h"
#include "conpty.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#define PENDING_BUF_SIZE  (64 * 1024)  /* 64KB max staged command */
#define HISTORY_CAP       256           /* command history ring */

/* ================================================================
 * GATE STATE
 * ================================================================ */

struct TerminalGate {
    TerminalGateMode  mode;
    Terminal         *terminal;

    /* Pending command buffer (staged, not yet executed) */
    char              pending[PENDING_BUF_SIZE];
    size_t            pending_len;
    bool              has_pending;

    /* Source tracking: who sent this command? */
    CommandSource     pending_source;

    /* History of confirmed/rejected commands */
    GateHistoryEntry  history[HISTORY_CAP];
    size_t            history_count;
    size_t            history_head;

    /* Statistics */
    size_t            total_staged;
    size_t            total_confirmed;
    size_t            total_rejected;
    size_t            total_bypassed;  /* user-direct, no gate */

    /* Callbacks */
    GateRenderCallback  render_cb;
    void               *render_ctx;
};

TerminalGate *gate_create(Terminal *terminal, TerminalGateMode mode) {
    TerminalGate *g = (TerminalGate *)calloc(1, sizeof(TerminalGate));
    if (!g) return NULL;

    g->terminal = terminal;
    g->mode = mode;
    g->has_pending = false;
    g->pending_len = 0;
    g->history_count = 0;
    g->history_head = 0;
    g->total_staged = 0;
    g->total_confirmed = 0;
    g->total_rejected = 0;
    g->total_bypassed = 0;
    g->render_cb = NULL;
    g->render_ctx = NULL;

    return g;
}

void gate_destroy(TerminalGate *g) {
    if (!g) return;
    free(g);
}

/* ================================================================
 * MODE CONTROL
 * ================================================================ */

void gate_set_mode(TerminalGate *g, TerminalGateMode mode) {
    if (!g) return;

    /* If switching from DIRECT to FALLBACK, flush nothing */
    /* If switching from FALLBACK to DIRECT, auto-confirm pending if any */
    if (g->mode == TERMINAL_MODE_FALLBACK && mode == TERMINAL_MODE_DIRECT) {
        if (g->has_pending) {
            gate_confirm(g);
        }
    }

    g->mode = mode;
}

TerminalGateMode gate_get_mode(const TerminalGate *g) {
    return g ? g->mode : TERMINAL_MODE_FALLBACK;
}

/* ================================================================
 * COMMAND STAGING
 *
 * agent_send_command() is called by the bridge when an agent
 * produces output that should go to the terminal. In FALLBACK mode,
 * this stages the command instead of executing it.
 * ================================================================ */

GateResult gate_stage_command(TerminalGate *g, const char *command, size_t len, CommandSource source) {
    if (!g || !command || len == 0) return GATE_ERR_INVALID;

    /* In DIRECT mode, execute immediately (no gate) */
    if (g->mode == TERMINAL_MODE_DIRECT && source == CMD_SOURCE_USER) {
        terminal_write(g->terminal, command, len);
        g->total_bypassed++;
        return GATE_OK_EXECUTED;
    }

    /* In DIRECT mode but from agent — still gate it for safety */
    if (g->mode == TERMINAL_MODE_DIRECT && source == CMD_SOURCE_AGENT) {
        /* Agent commands ALWAYS get staged, even in DIRECT mode */
        /* This is the security invariant */
    }

    /* FALLBACK or PREVIEW mode: stage the command */
    if (g->has_pending) {
        /* Already have a pending command — reject (one at a time) */
        return GATE_ERR_PENDING_FULL;
    }

    if (len >= PENDING_BUF_SIZE) {
        return GATE_ERR_TOO_LARGE;
    }

    memcpy(g->pending, command, len);
    g->pending_len = len;
    g->pending[len] = '\0';  /* null-terminate for display */
    g->has_pending = true;
    g->pending_source = source;
    g->total_staged++;

    /* Notify render callback so UI can highlight the staged command */
    if (g->render_cb) {
        g->render_cb(g->render_ctx, g->pending, g->pending_len, source);
    }

    return GATE_OK_STAGED;
}

/* ================================================================
 * USER ACTIONS — confirm, reject, edit
 * ================================================================ */

GateResult gate_confirm(TerminalGate *g) {
    if (!g || !g->has_pending) return GATE_ERR_NO_PENDING;

    if (g->mode == TERMINAL_MODE_PREVIEW) {
        /* Preview mode: never execute, only copy */
        return GATE_ERR_PREVIEW_MODE;
    }

    /* Execute: write staged command to terminal + newline */
    terminal_write(g->terminal, g->pending, g->pending_len);
    terminal_write(g->terminal, "\r\n", 2);

    /* Record in history */
    gate_record_history(g, g->pending, g->pending_len, g->pending_source, true);

    /* Clear pending */
    g->has_pending = false;
    g->pending_len = 0;
    g->total_confirmed++;

    return GATE_OK_EXECUTED;
}

GateResult gate_reject(TerminalGate *g) {
    if (!g || !g->has_pending) return GATE_ERR_NO_PENDING;

    /* Record rejection in history */
    gate_record_history(g, g->pending, g->pending_len, g->pending_source, false);

    /* Clear pending without executing */
    g->has_pending = false;
    g->pending_len = 0;
    g->total_rejected++;

    /* Notify render to clear staged display */
    if (g->render_cb) {
        g->render_cb(g->render_ctx, NULL, 0, CMD_SOURCE_USER);
    }

    return GATE_OK_REJECTED;
}

GateResult gate_edit_pending(TerminalGate *g, const char *new_command, size_t new_len) {
    if (!g || !g->has_pending) return GATE_ERR_NO_PENDING;
    if (!new_command || new_len == 0) return gate_reject(g);
    if (new_len >= PENDING_BUF_SIZE) return GATE_ERR_TOO_LARGE;

    memcpy(g->pending, new_command, new_len);
    g->pending_len = new_len;
    g->pending[new_len] = '\0';

    /* Re-render with edited content */
    if (g->render_cb) {
        g->render_cb(g->render_ctx, g->pending, g->pending_len, g->pending_source);
    }

    return GATE_OK_STAGED;
}

/* ================================================================
 * POPULATE-ONLY MODE (Ctrl+K D)
 *
 * Routes text to terminal input line WITHOUT appending \r\n.
 * The user sees it in their prompt and must press Enter manually.
 * This is the "Manual Send Shortcut" from the spec.
 * ================================================================ */

GateResult gate_populate_only(TerminalGate *g, const char *text, size_t len) {
    if (!g || !text || len == 0) return GATE_ERR_INVALID;

    /* Write to terminal WITHOUT newline — just populates the input line */
    terminal_write(g->terminal, text, len);

    /* This bypasses the staging system entirely — it's user-triggered */
    g->total_bypassed++;
    return GATE_OK_POPULATED;
}

/* ================================================================
 * USER KEYSTROKES — always bypass gate
 *
 * When the user types directly in the terminal, their keystrokes
 * go straight to ConPTY. The gate only intercepts agent-originated
 * payloads. This function is the "bypass" path.
 * ================================================================ */

GateResult gate_user_keystroke(TerminalGate *g, const char *data, size_t len) {
    if (!g || !data || len == 0) return GATE_ERR_INVALID;

    /* User input always goes direct — no staging, no confirmation */
    terminal_write(g->terminal, data, len);
    return GATE_OK_EXECUTED;
}

/* ================================================================
 * QUERY STATE
 * ================================================================ */

bool gate_has_pending(const TerminalGate *g) {
    return g && g->has_pending;
}

const char *gate_get_pending(const TerminalGate *g, size_t *out_len) {
    if (!g || !g->has_pending) {
        if (out_len) *out_len = 0;
        return NULL;
    }
    if (out_len) *out_len = g->pending_len;
    return g->pending;
}

CommandSource gate_get_pending_source(const TerminalGate *g) {
    return (g && g->has_pending) ? g->pending_source : CMD_SOURCE_USER;
}

/* ================================================================
 * HISTORY
 * ================================================================ */

static void gate_record_history(TerminalGate *g, const char *cmd, size_t len, CommandSource source, bool confirmed) {
    GateHistoryEntry *entry = &g->history[g->history_head % HISTORY_CAP];

    /* Truncate command for history storage */
    size_t store_len = (len < sizeof(entry->command) - 1) ? len : sizeof(entry->command) - 1;
    memcpy(entry->command, cmd, store_len);
    entry->command[store_len] = '\0';
    entry->command_len = store_len;
    entry->source = source;
    entry->confirmed = confirmed;
    entry->index = g->history_count;

    g->history_head++;
    if (g->history_count < HISTORY_CAP) g->history_count++;
}

size_t gate_get_history_count(const TerminalGate *g) {
    return g ? g->history_count : 0;
}

const GateHistoryEntry *gate_get_history_entry(const TerminalGate *g, size_t index) {
    if (!g || index >= g->history_count) return NULL;

    /* Walk backward from head */
    size_t slot;
    if (g->history_count < HISTORY_CAP) {
        slot = index;
    } else {
        slot = (g->history_head - g->history_count + index) % HISTORY_CAP;
    }
    return &g->history[slot];
}

/* ================================================================
 * RENDER CALLBACK
 * ================================================================ */

void gate_set_render_callback(TerminalGate *g, GateRenderCallback cb, void *ctx) {
    if (!g) return;
    g->render_cb = cb;
    g->render_ctx = ctx;
}

/* ================================================================
 * STATISTICS
 * ================================================================ */

void gate_get_stats(const TerminalGate *g, GateStats *out) {
    if (!g || !out) return;
    out->total_staged = g->total_staged;
    out->total_confirmed = g->total_confirmed;
    out->total_rejected = g->total_rejected;
    out->total_bypassed = g->total_bypassed;
    out->mode = g->mode;
    out->has_pending = g->has_pending;
}

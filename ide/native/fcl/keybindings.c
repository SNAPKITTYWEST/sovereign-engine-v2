/*
 * Sovereign IDE — Keybindings Configuration
 *
 * Phase 2: Shortcut routing for agent-terminal control flow.
 *
 * Key mappings:
 *   Ctrl+K D       — Populate terminal (no execute). Manual Send Shortcut.
 *   Ctrl+Shift+A   — Quick Action: send selection to agent
 *   Enter          — Confirm staged command (when pending)
 *   Escape         — Reject staged command (when pending)
 *   Ctrl+Shift+E   — Toggle terminal mode (DIRECT <-> FALLBACK)
 *   Ctrl+Shift+P   — Preview mode (read-only terminal)
 *
 * Keybindings are evaluated as a chord sequence. Ctrl+K is the
 * prefix chord — after Ctrl+K, the next key completes the binding.
 *
 * All bindings are configurable via FCL rules. This file provides
 * the default set and the dispatch mechanism.
 */

#include "keybindings.h"
#include "../terminal/fallback_gate.h"
#include "../editor/code_ref_parser.h"
#include <string.h>
#include <stdlib.h>

#define MAX_BINDINGS 128

/* ================================================================
 * KEY CHORD REPRESENTATION
 * ================================================================ */

typedef struct {
    uint8_t  modifiers;     /* MOD_CTRL | MOD_SHIFT | MOD_ALT */
    uint16_t key;           /* virtual keycode */
} KeyChord;

typedef struct {
    KeyChord   chord;
    KeyChord   second;      /* for two-key sequences like Ctrl+K, D */
    bool       is_sequence; /* true if this is a two-key binding */
    BindAction action;
    char       description[128];
} KeyBinding;

struct KeybindingTable {
    KeyBinding  bindings[MAX_BINDINGS];
    size_t      count;
    bool        awaiting_second;  /* true after first chord of a sequence */
    KeyChord    first_chord;      /* the first chord (e.g., Ctrl+K) */

    /* Callbacks into IDE systems */
    TerminalGate        *gate;
    KeybindActionCallback action_cb;
    void                *action_ctx;
};

/* Modifier flags */
#define MOD_CTRL  0x01
#define MOD_SHIFT 0x02
#define MOD_ALT   0x04

/* Virtual key codes (Windows VK_ style) */
#define VK_K       0x4B
#define VK_D       0x44
#define VK_A       0x41
#define VK_E       0x45
#define VK_P       0x50
#define VK_RETURN  0x0D
#define VK_ESCAPE  0x1B

/* ================================================================
 * DEFAULT BINDINGS
 * ================================================================ */

static const struct {
    uint8_t  mod1;
    uint16_t key1;
    uint8_t  mod2;
    uint16_t key2;
    bool     is_seq;
    BindAction action;
    const char *desc;
} DEFAULT_BINDINGS[] = {
    /* Ctrl+K, D — populate terminal without execute */
    { MOD_CTRL, VK_K, 0, VK_D, true, BIND_TERMINAL_POPULATE,
      "Populate terminal input (no execute)" },

    /* Ctrl+Shift+A — quick action on selection */
    { MOD_CTRL | MOD_SHIFT, VK_A, 0, 0, false, BIND_QUICK_ACTION,
      "Send selection to agent (quick action)" },

    /* Enter — confirm staged command */
    { 0, VK_RETURN, 0, 0, false, BIND_GATE_CONFIRM,
      "Confirm staged terminal command" },

    /* Escape — reject staged command */
    { 0, VK_ESCAPE, 0, 0, false, BIND_GATE_REJECT,
      "Reject staged terminal command" },

    /* Ctrl+Shift+E — toggle fallback mode */
    { MOD_CTRL | MOD_SHIFT, VK_E, 0, 0, false, BIND_TOGGLE_GATE_MODE,
      "Toggle terminal gate mode (Direct/Fallback)" },

    /* Ctrl+Shift+P — preview mode */
    { MOD_CTRL | MOD_SHIFT, VK_P, 0, 0, false, BIND_PREVIEW_MODE,
      "Set terminal to preview mode (read-only)" },
};

#define DEFAULT_BINDING_COUNT (sizeof(DEFAULT_BINDINGS) / sizeof(DEFAULT_BINDINGS[0]))

/* ================================================================
 * LIFECYCLE
 * ================================================================ */

KeybindingTable *keybindings_create(TerminalGate *gate) {
    KeybindingTable *t = (KeybindingTable *)calloc(1, sizeof(KeybindingTable));
    if (!t) return NULL;

    t->gate = gate;
    t->count = 0;
    t->awaiting_second = false;

    /* Load defaults */
    for (size_t i = 0; i < DEFAULT_BINDING_COUNT && t->count < MAX_BINDINGS; i++) {
        KeyBinding *b = &t->bindings[t->count++];
        b->chord.modifiers = DEFAULT_BINDINGS[i].mod1;
        b->chord.key = DEFAULT_BINDINGS[i].key1;
        b->second.modifiers = DEFAULT_BINDINGS[i].mod2;
        b->second.key = DEFAULT_BINDINGS[i].key2;
        b->is_sequence = DEFAULT_BINDINGS[i].is_seq;
        b->action = DEFAULT_BINDINGS[i].action;
        strncpy(b->description, DEFAULT_BINDINGS[i].desc, sizeof(b->description) - 1);
    }

    return t;
}

void keybindings_destroy(KeybindingTable *t) {
    free(t);
}

void keybindings_set_callback(KeybindingTable *t, KeybindActionCallback cb, void *ctx) {
    if (!t) return;
    t->action_cb = cb;
    t->action_ctx = ctx;
}

/* ================================================================
 * KEY DISPATCH
 *
 * Called by the window message loop for every key event.
 * Returns true if the key was consumed by a binding.
 * Returns false if it should be passed through to the focused widget.
 * ================================================================ */

static bool chord_matches(KeyChord binding, uint8_t modifiers, uint16_t key) {
    return binding.modifiers == modifiers && binding.key == key;
}

KeyDispatchResult keybindings_dispatch(KeybindingTable *t, uint8_t modifiers, uint16_t key) {
    if (!t) return KEY_PASS_THROUGH;

    /* Check if we're in a sequence (waiting for second key) */
    if (t->awaiting_second) {
        t->awaiting_second = false;

        /* Look for binding that matches first + second */
        for (size_t i = 0; i < t->count; i++) {
            KeyBinding *b = &t->bindings[i];
            if (!b->is_sequence) continue;
            if (!chord_matches(b->chord, t->first_chord.modifiers, t->first_chord.key)) continue;
            if (!chord_matches(b->second, modifiers, key)) continue;

            /* Match! Execute action. */
            if (t->action_cb) {
                t->action_cb(t->action_ctx, b->action);
            }
            return KEY_CONSUMED;
        }

        /* No match for second key — pass through */
        return KEY_PASS_THROUGH;
    }

    /* Check single-key bindings and sequence starts */
    for (size_t i = 0; i < t->count; i++) {
        KeyBinding *b = &t->bindings[i];
        if (!chord_matches(b->chord, modifiers, key)) continue;

        if (b->is_sequence) {
            /* Start of a sequence — wait for next key */
            t->awaiting_second = true;
            t->first_chord.modifiers = modifiers;
            t->first_chord.key = key;
            return KEY_CONSUMED;
        }

        /* Context-sensitive: Enter/Escape only consumed when gate has pending */
        if (b->action == BIND_GATE_CONFIRM || b->action == BIND_GATE_REJECT) {
            if (!gate_has_pending(t->gate)) {
                return KEY_PASS_THROUGH;
            }
        }

        /* Single-key binding — execute immediately */
        if (t->action_cb) {
            t->action_cb(t->action_ctx, b->action);
        }
        return KEY_CONSUMED;
    }

    return KEY_PASS_THROUGH;
}

/* ================================================================
 * BINDING MANAGEMENT
 * ================================================================ */

bool keybindings_add(KeybindingTable *t, uint8_t mod1, uint16_t key1,
                     uint8_t mod2, uint16_t key2, bool is_seq,
                     BindAction action, const char *desc) {
    if (!t || t->count >= MAX_BINDINGS) return false;

    KeyBinding *b = &t->bindings[t->count++];
    b->chord.modifiers = mod1;
    b->chord.key = key1;
    b->second.modifiers = mod2;
    b->second.key = key2;
    b->is_sequence = is_seq;
    b->action = action;
    if (desc) strncpy(b->description, desc, sizeof(b->description) - 1);

    return true;
}

bool keybindings_remove(KeybindingTable *t, BindAction action) {
    if (!t) return false;

    for (size_t i = 0; i < t->count; i++) {
        if (t->bindings[i].action == action) {
            /* Shift remaining entries */
            memmove(&t->bindings[i], &t->bindings[i + 1],
                    (t->count - i - 1) * sizeof(KeyBinding));
            t->count--;
            return true;
        }
    }
    return false;
}

size_t keybindings_count(const KeybindingTable *t) {
    return t ? t->count : 0;
}

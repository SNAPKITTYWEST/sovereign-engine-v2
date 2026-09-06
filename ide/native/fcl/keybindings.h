/*
 * Sovereign IDE — Keybindings Header
 * Phase 2: User-control shortcuts for agent-terminal flow
 */

#ifndef SOVEREIGN_KEYBINDINGS_H
#define SOVEREIGN_KEYBINDINGS_H

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct TerminalGate TerminalGate;
typedef struct KeybindingTable KeybindingTable;

/* Actions triggered by key bindings */
typedef enum {
    BIND_TERMINAL_POPULATE = 0, /* Ctrl+K D: populate without execute */
    BIND_QUICK_ACTION      = 1, /* Ctrl+Shift+A: selection -> agent */
    BIND_GATE_CONFIRM      = 2, /* Enter: confirm staged command */
    BIND_GATE_REJECT       = 3, /* Escape: reject staged command */
    BIND_TOGGLE_GATE_MODE  = 4, /* Ctrl+Shift+E: toggle Direct/Fallback */
    BIND_PREVIEW_MODE      = 5, /* Ctrl+Shift+P: read-only terminal */
} BindAction;

/* Dispatch result */
typedef enum {
    KEY_CONSUMED     = 0, /* binding handled the key */
    KEY_PASS_THROUGH = 1, /* no binding matched, pass to widget */
} KeyDispatchResult;

/* Callback when a binding fires */
typedef void (*KeybindActionCallback)(void *ctx, BindAction action);

/* Lifecycle */
KeybindingTable *keybindings_create(TerminalGate *gate);
void             keybindings_destroy(KeybindingTable *t);
void             keybindings_set_callback(KeybindingTable *t, KeybindActionCallback cb, void *ctx);

/* Dispatch (called from window message loop) */
KeyDispatchResult keybindings_dispatch(KeybindingTable *t, uint8_t modifiers, uint16_t key);

/* Management */
bool   keybindings_add(KeybindingTable *t, uint8_t mod1, uint16_t key1,
                       uint8_t mod2, uint16_t key2, bool is_seq,
                       BindAction action, const char *desc);
bool   keybindings_remove(KeybindingTable *t, BindAction action);
size_t keybindings_count(const KeybindingTable *t);

#endif /* SOVEREIGN_KEYBINDINGS_H */

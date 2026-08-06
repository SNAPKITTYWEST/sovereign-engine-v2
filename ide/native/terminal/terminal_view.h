#ifndef SOVEREIGN_TERMINAL_VIEW_H
#define SOVEREIGN_TERMINAL_VIEW_H

#include <windows.h>
#include <stdbool.h>
#include <stdint.h>
#include "../core/errors.h"

typedef struct TerminalView TerminalView;

SovResult terminal_view_create(TerminalView **out, HWND hwnd);
void      terminal_view_destroy(TerminalView *tv);
void      terminal_view_paint(TerminalView *tv);
void      terminal_view_resize(TerminalView *tv, int w, int h);
void      terminal_view_key_down(TerminalView *tv, UINT vk, UINT mods);
void      terminal_view_char(TerminalView *tv, wchar_t ch);
void      terminal_view_tick(TerminalView *tv);   /* poll ConPTY, feed parser */

#endif

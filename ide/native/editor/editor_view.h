#ifndef SOVEREIGN_EDITOR_VIEW_H
#define SOVEREIGN_EDITOR_VIEW_H

#include "document.h"
#include "../core/errors.h"
#include "../lsp/client.h"
#include <windows.h>
#include <stdbool.h>
#include <stdint.h>

typedef struct EditorView EditorView;

SovResult editor_view_create(EditorView **out, HWND hwnd);
void      editor_view_destroy(EditorView *ev);
void      editor_view_set_document(EditorView *ev, Document *doc);
void      editor_view_set_diagnostics(EditorView *ev, const LspDiagList *list);
void      editor_view_paint(EditorView *ev, RECT client);
void      editor_view_resize(EditorView *ev, uint32_t w, uint32_t h);

void      editor_view_key_down(EditorView *ev, UINT vk, UINT mods);
void      editor_view_char(EditorView *ev, wchar_t ch);
void      editor_view_mouse_down(EditorView *ev, int x, int y);
void      editor_view_mouse_move(EditorView *ev, int x, int y, bool btn);

size_t    editor_view_caret_offset(const EditorView *ev);

#endif

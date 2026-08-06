#ifndef SOVEREIGN_STATUS_BAR_H
#define SOVEREIGN_STATUS_BAR_H

#include <windows.h>
#include "../core/errors.h"

typedef struct StatusBar StatusBar;

SovResult status_bar_create(StatusBar **out, HWND hwnd);
void      status_bar_destroy(StatusBar *sb);
void      status_bar_set_file(StatusBar *sb, const wchar_t *name, bool dirty);
void      status_bar_set_pos(StatusBar *sb, int line, int col);
void      status_bar_set_message(StatusBar *sb, const wchar_t *msg);
void      status_bar_set_branch(StatusBar *sb, const wchar_t *branch);
void      status_bar_paint(StatusBar *sb);
void      status_bar_resize(StatusBar *sb, int w, int h);

#endif

#ifndef SOVEREIGN_OUTPUT_PANEL_H
#define SOVEREIGN_OUTPUT_PANEL_H

#include <windows.h>
#include "../core/errors.h"

typedef struct OutputPanel OutputPanel;

SovResult output_panel_create(OutputPanel **out, HWND hwnd);
void      output_panel_destroy(OutputPanel *op);
void      output_panel_append(OutputPanel *op, const wchar_t *text);
void      output_panel_clear(OutputPanel *op);
void      output_panel_paint(OutputPanel *op);
void      output_panel_resize(OutputPanel *op, int w, int h);
void      output_panel_scroll(OutputPanel *op, int delta);

#endif

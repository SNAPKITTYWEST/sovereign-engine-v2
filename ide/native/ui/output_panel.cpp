/*
 * Sovereign IDE — Output Panel
 * Scrollable read-only text for build output, terminal output, diagnostics.
 */

#include <windows.h>
#include <d2d1.h>
#include <dwrite.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

extern "C" {
#include "output_panel.h"
}

#define MAX_LINES   4096
#define MAX_LINE_W  2048
#define ROW_H       16.0f

static const D2D1_COLOR_F C_BG   = { 0.071f, 0.071f, 0.086f, 1.0f };
static const D2D1_COLOR_F C_TEXT = { 0.780f, 0.780f, 0.780f, 1.0f };
static const D2D1_COLOR_F C_ERR  = { 1.000f, 0.400f, 0.400f, 1.0f };
static const D2D1_COLOR_F C_WARN = { 1.000f, 0.820f, 0.400f, 1.0f };

struct OutputPanel {
    HWND hwnd;
    ID2D1Factory          *d2d;
    ID2D1HwndRenderTarget *rt;
    IDWriteFactory        *dw;
    IDWriteTextFormat     *fmt;
    ID2D1SolidColorBrush  *br_bg;
    ID2D1SolidColorBrush  *br_text;
    ID2D1SolidColorBrush  *br_err;
    ID2D1SolidColorBrush  *br_warn;

    wchar_t lines[MAX_LINES][MAX_LINE_W];
    int     line_count;
    int     scroll_top;
};

extern "C" SovResult output_panel_create(OutputPanel **out, HWND hwnd) {
    OutputPanel *op = (OutputPanel *)calloc(1, sizeof(OutputPanel));
    if (!op) return SOV_ERR_ALLOC;
    op->hwnd = hwnd;

    D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &op->d2d);
    DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown**>(&op->dw));
    op->dw->CreateTextFormat(L"Consolas", nullptr,
        DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL, DWRITE_FONT_STRETCH_NORMAL,
        12.0f, L"en-us", &op->fmt);
    op->fmt->SetWordWrapping(DWRITE_WORD_WRAPPING_NO_WRAP);

    RECT rc; GetClientRect(hwnd, &rc);
    op->d2d->CreateHwndRenderTarget(
        D2D1::RenderTargetProperties(),
        D2D1::HwndRenderTargetProperties(hwnd,
            D2D1::SizeU(rc.right - rc.left, rc.bottom - rc.top)),
        &op->rt);
    if (op->rt) {
        op->rt->CreateSolidColorBrush(C_BG,   &op->br_bg);
        op->rt->CreateSolidColorBrush(C_TEXT, &op->br_text);
        op->rt->CreateSolidColorBrush(C_ERR,  &op->br_err);
        op->rt->CreateSolidColorBrush(C_WARN, &op->br_warn);
    }
    *out = op;
    return SOV_OK;
}

extern "C" void output_panel_destroy(OutputPanel *op) {
    if (!op) return;
    if (op->br_bg)   op->br_bg->Release();
    if (op->br_text) op->br_text->Release();
    if (op->br_err)  op->br_err->Release();
    if (op->br_warn) op->br_warn->Release();
    if (op->fmt)     op->fmt->Release();
    if (op->rt)      op->rt->Release();
    if (op->d2d)     op->d2d->Release();
    if (op->dw)      op->dw->Release();
    free(op);
}

extern "C" void output_panel_append(OutputPanel *op, const wchar_t *text) {
    /* Split on newlines */
    const wchar_t *p = text;
    while (*p) {
        if (op->line_count >= MAX_LINES) {
            /* drop oldest */
            memmove(op->lines[0], op->lines[1], (MAX_LINES - 1) * MAX_LINE_W * sizeof(wchar_t));
            op->line_count = MAX_LINES - 1;
        }
        const wchar_t *nl = wcschr(p, L'\n');
        size_t chunk = nl ? (size_t)(nl - p) : wcslen(p);
        if (chunk >= MAX_LINE_W) chunk = MAX_LINE_W - 1;
        wcsncpy_s(op->lines[op->line_count], MAX_LINE_W, p, chunk);
        op->line_count++;
        if (!nl) break;
        p = nl + 1;
    }
    /* auto-scroll to bottom */
    op->scroll_top = op->line_count;
    InvalidateRect(op->hwnd, NULL, FALSE);
}

extern "C" void output_panel_clear(OutputPanel *op) {
    op->line_count = 0;
    op->scroll_top = 0;
    InvalidateRect(op->hwnd, NULL, FALSE);
}

extern "C" void output_panel_scroll(OutputPanel *op, int delta) {
    op->scroll_top -= delta;
    if (op->scroll_top < 0) op->scroll_top = 0;
    if (op->scroll_top > op->line_count) op->scroll_top = op->line_count;
    InvalidateRect(op->hwnd, NULL, FALSE);
}

extern "C" void output_panel_resize(OutputPanel *op, int w, int h) {
    if (op->rt) op->rt->Resize(D2D1::SizeU((UINT32)w, (UINT32)h));
}

extern "C" void output_panel_paint(OutputPanel *op) {
    if (!op->rt && op->d2d) {
        RECT rc; GetClientRect(op->hwnd, &rc);
        UINT W = rc.right  > rc.left ? (UINT)(rc.right  - rc.left) : 1;
        UINT H = rc.bottom > rc.top  ? (UINT)(rc.bottom - rc.top)  : 1;
        op->d2d->CreateHwndRenderTarget(D2D1::RenderTargetProperties(),
            D2D1::HwndRenderTargetProperties(op->hwnd, D2D1::SizeU(W, H)), &op->rt);
        if (op->rt) {
            op->rt->CreateSolidColorBrush(C_BG,   &op->br_bg);
            op->rt->CreateSolidColorBrush(C_TEXT, &op->br_text);
            op->rt->CreateSolidColorBrush(C_ERR,  &op->br_err);
            op->rt->CreateSolidColorBrush(C_WARN, &op->br_warn);
        }
    }
    if (!op->rt) return;
    op->rt->BeginDraw();
    op->rt->Clear(&C_BG);

    RECT rc; GetClientRect(op->hwnd, &rc);
    int visible = (int)((rc.bottom - rc.top) / ROW_H) + 1;
    int first = op->scroll_top - visible;
    if (first < 0) first = 0;

    for (int i = first; i < op->line_count && i < first + visible; i++) {
        float y = (float)(i - first) * ROW_H;
        const wchar_t *line = op->lines[i];
        UINT32 len = (UINT32)wcslen(line);
        if (len == 0) continue;

        ID2D1SolidColorBrush *br = op->br_text;
        /* simple color coding */
        if (wcsstr(line, L"error") || wcsstr(line, L"Error"))   br = op->br_err;
        if (wcsstr(line, L"warning") || wcsstr(line, L"Warning")) br = op->br_warn;

        D2D1_RECT_F r = D2D1::RectF(4.0f, y, (float)rc.right - 4.0f, y + ROW_H);
        op->rt->DrawText(line, len, op->fmt, r, br);
    }

    op->rt->EndDraw(nullptr, nullptr);
}

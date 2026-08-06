/*
 * Sovereign IDE — Status Bar
 * Single-row bottom strip: filename, dirty, line/col, branch, message.
 */

#include <windows.h>
#include <d2d1.h>
#include <dwrite.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

extern "C" {
#include "status_bar.h"
}

static const D2D1_COLOR_F C_BG   = { 0.118f, 0.294f, 0.510f, 1.0f }; /* VS-Code-like blue */
static const D2D1_COLOR_F C_TEXT = { 1.000f, 1.000f, 1.000f, 1.0f };

struct StatusBar {
    HWND hwnd;
    ID2D1Factory          *d2d;
    ID2D1HwndRenderTarget *rt;
    IDWriteFactory        *dw;
    IDWriteTextFormat     *fmt;
    ID2D1SolidColorBrush  *br_bg;
    ID2D1SolidColorBrush  *br_text;
    wchar_t file_name[MAX_PATH];
    bool    dirty;
    int     line, col;
    wchar_t message[256];
    wchar_t branch[128];
};

extern "C" SovResult status_bar_create(StatusBar **out, HWND hwnd) {
    StatusBar *sb = (StatusBar *)calloc(1, sizeof(StatusBar));
    if (!sb) return SOV_ERR_ALLOC;
    sb->hwnd = hwnd;
    sb->line = 1; sb->col = 1;

    D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &sb->d2d);
    DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown**>(&sb->dw));
    sb->dw->CreateTextFormat(L"Segoe UI", nullptr,
        DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL, DWRITE_FONT_STRETCH_NORMAL,
        11.0f, L"en-us", &sb->fmt);

    RECT rc; GetClientRect(hwnd, &rc);
    sb->d2d->CreateHwndRenderTarget(
        D2D1::RenderTargetProperties(),
        D2D1::HwndRenderTargetProperties(hwnd,
            D2D1::SizeU(rc.right - rc.left, rc.bottom - rc.top)),
        &sb->rt);
    if (sb->rt) {
        sb->rt->CreateSolidColorBrush(C_BG,   &sb->br_bg);
        sb->rt->CreateSolidColorBrush(C_TEXT, &sb->br_text);
    }
    *out = sb;
    return SOV_OK;
}

extern "C" void status_bar_destroy(StatusBar *sb) {
    if (!sb) return;
    if (sb->br_bg)   sb->br_bg->Release();
    if (sb->br_text) sb->br_text->Release();
    if (sb->fmt)     sb->fmt->Release();
    if (sb->rt)      sb->rt->Release();
    if (sb->d2d)     sb->d2d->Release();
    if (sb->dw)      sb->dw->Release();
    free(sb);
}

extern "C" void status_bar_set_file(StatusBar *sb, const wchar_t *name, bool dirty) {
    wcscpy_s(sb->file_name, MAX_PATH, name ? name : L"untitled");
    sb->dirty = dirty;
    InvalidateRect(sb->hwnd, NULL, FALSE);
}

extern "C" void status_bar_set_pos(StatusBar *sb, int line, int col) {
    sb->line = line; sb->col = col;
    InvalidateRect(sb->hwnd, NULL, FALSE);
}

extern "C" void status_bar_set_message(StatusBar *sb, const wchar_t *msg) {
    wcscpy_s(sb->message, 256, msg ? msg : L"");
    InvalidateRect(sb->hwnd, NULL, FALSE);
}

extern "C" void status_bar_set_branch(StatusBar *sb, const wchar_t *branch) {
    wcscpy_s(sb->branch, 128, branch ? branch : L"");
    InvalidateRect(sb->hwnd, NULL, FALSE);
}

extern "C" void status_bar_resize(StatusBar *sb, int w, int h) {
    if (sb->rt) sb->rt->Resize(D2D1::SizeU((UINT32)w, (UINT32)h));
}

extern "C" void status_bar_paint(StatusBar *sb) {
    if (!sb->rt && sb->d2d) {
        RECT rc; GetClientRect(sb->hwnd, &rc);
        UINT W = rc.right  > rc.left ? (UINT)(rc.right  - rc.left) : 1;
        UINT H = rc.bottom > rc.top  ? (UINT)(rc.bottom - rc.top)  : 1;
        sb->d2d->CreateHwndRenderTarget(D2D1::RenderTargetProperties(),
            D2D1::HwndRenderTargetProperties(sb->hwnd, D2D1::SizeU(W, H)), &sb->rt);
        if (sb->rt) {
            sb->rt->CreateSolidColorBrush(C_BG,   &sb->br_bg);
            sb->rt->CreateSolidColorBrush(C_TEXT, &sb->br_text);
        }
    }
    if (!sb->rt) return;
    sb->rt->BeginDraw();
    sb->rt->Clear(&C_BG);

    RECT rc; GetClientRect(sb->hwnd, &rc);
    float H = (float)(rc.bottom - rc.top);
    float y = 4.0f;

    /* Branch on left */
    if (sb->branch[0]) {
        wchar_t buf[160];
        swprintf_s(buf, 160, L"  ⎇ %s", sb->branch);
        D2D1_RECT_F r = D2D1::RectF(0, y, 200.0f, H);
        sb->rt->DrawText(buf, (UINT32)wcslen(buf), sb->fmt, r, sb->br_text);
    }

    /* Filename + dirty */
    {
        wchar_t buf[MAX_PATH + 4];
        swprintf_s(buf, MAX_PATH + 4, L"%s%s", sb->dirty ? L"● " : L"", sb->file_name);
        float W = (float)rc.right;
        D2D1_RECT_F r = D2D1::RectF(W / 2.0f - 200.0f, y, W / 2.0f + 200.0f, H);
        sb->fmt->SetTextAlignment(DWRITE_TEXT_ALIGNMENT_CENTER);
        sb->rt->DrawText(buf, (UINT32)wcslen(buf), sb->fmt, r, sb->br_text);
        sb->fmt->SetTextAlignment(DWRITE_TEXT_ALIGNMENT_LEADING);
    }

    /* Line:Col + message on right */
    {
        wchar_t buf[300];
        swprintf_s(buf, 300, L"Ln %d, Col %d  %s  ", sb->line, sb->col, sb->message);
        float W = (float)rc.right;
        D2D1_RECT_F r = D2D1::RectF(W - 320.0f, y, W, H);
        sb->fmt->SetTextAlignment(DWRITE_TEXT_ALIGNMENT_TRAILING);
        sb->rt->DrawText(buf, (UINT32)wcslen(buf), sb->fmt, r, sb->br_text);
        sb->fmt->SetTextAlignment(DWRITE_TEXT_ALIGNMENT_LEADING);
    }

    sb->rt->EndDraw(nullptr, nullptr);
}

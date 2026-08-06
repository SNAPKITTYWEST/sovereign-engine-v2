/*
 * Sovereign IDE — Editor View
 * DirectWrite text rendering, visible caret, selection, keyboard navigation.
 * C++ for COM vtable calls; all public functions are extern "C".
 */

#include <windows.h>
#include <d2d1.h>
#include <dwrite.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

extern "C" {
#include "editor_view.h"
#include "document.h"
#include "buffer.h"
#include "../lsp/client.h"
}

#define FONT_SIZE     14.0f
#define LINE_HEIGHT   20.0f
#define GUTTER_WIDTH  48.0f
#define PADDING_LEFT   4.0f
#define CARET_WIDTH    2.0f
#define SCROLL_LINES   3

/* Colors (dark theme) */
static const D2D1_COLOR_F C_BG         = { 0.122f, 0.122f, 0.141f, 1.0f };
static const D2D1_COLOR_F C_GUTTER     = { 0.098f, 0.098f, 0.118f, 1.0f };
static const D2D1_COLOR_F C_GUTTER_FG  = { 0.420f, 0.420f, 0.520f, 1.0f };
static const D2D1_COLOR_F C_TEXT       = { 0.859f, 0.859f, 0.859f, 1.0f };
static const D2D1_COLOR_F C_CARET      = { 1.000f, 1.000f, 1.000f, 1.0f };
static const D2D1_COLOR_F C_SEL        = { 0.173f, 0.369f, 0.529f, 0.6f };
static const D2D1_COLOR_F C_ACTIVE_LINE= { 1.000f, 1.000f, 1.000f, 0.04f };
static const D2D1_COLOR_F C_SQUIGGLE_E = { 1.000f, 0.260f, 0.260f, 1.0f }; /* error   */
static const D2D1_COLOR_F C_SQUIGGLE_W = { 1.000f, 0.780f, 0.200f, 1.0f }; /* warning */

struct EditorView {
    HWND                    hwnd;
    Document               *doc;

    ID2D1Factory           *d2d_factory;
    ID2D1HwndRenderTarget  *rt;
    IDWriteFactory         *dw_factory;
    IDWriteTextFormat      *text_format;
    IDWriteTextFormat      *gutter_format;

    ID2D1SolidColorBrush   *br_text;
    ID2D1SolidColorBrush   *br_gutter_fg;
    ID2D1SolidColorBrush   *br_caret;
    ID2D1SolidColorBrush   *br_sel;
    ID2D1SolidColorBrush   *br_active_line;
    ID2D1SolidColorBrush   *br_gutter_bg;
    ID2D1SolidColorBrush   *br_squiggle_e;
    ID2D1SolidColorBrush   *br_squiggle_w;

    uint32_t    width;
    uint32_t    height;
    float       scroll_y;       /* in lines */

    size_t      caret;          /* byte offset in buffer */
    size_t      sel_anchor;     /* selection start; equals caret = no selection */
    bool        has_sel;

    bool        caret_visible;  /* blink state */
    DWORD       caret_tick;

    /* LSP diagnostics for current file */
    LspDiagList diags;
    bool        has_diags;
};

static HRESULT create_brushes(EditorView *ev) {
    HRESULT hr;
    hr = ev->rt->CreateSolidColorBrush(C_TEXT,        &ev->br_text);         if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_GUTTER_FG,   &ev->br_gutter_fg);    if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_CARET,       &ev->br_caret);        if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_SEL,         &ev->br_sel);          if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_ACTIVE_LINE, &ev->br_active_line);  if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_GUTTER,      &ev->br_gutter_bg);    if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_SQUIGGLE_E,  &ev->br_squiggle_e);   if (FAILED(hr)) return hr;
    hr = ev->rt->CreateSolidColorBrush(C_SQUIGGLE_W,  &ev->br_squiggle_w);   if (FAILED(hr)) return hr;
    return S_OK;
}

static void release_brushes(EditorView *ev) {
    auto safe = [](IUnknown *p) { if (p) p->Release(); };
    safe(ev->br_text);        ev->br_text        = nullptr;
    safe(ev->br_gutter_fg);   ev->br_gutter_fg   = nullptr;
    safe(ev->br_caret);       ev->br_caret       = nullptr;
    safe(ev->br_sel);         ev->br_sel         = nullptr;
    safe(ev->br_active_line); ev->br_active_line = nullptr;
    safe(ev->br_gutter_bg);   ev->br_gutter_bg   = nullptr;
    safe(ev->br_squiggle_e);  ev->br_squiggle_e  = nullptr;
    safe(ev->br_squiggle_w);  ev->br_squiggle_w  = nullptr;
}

extern "C" SovResult editor_view_create(EditorView **out, HWND hwnd) {
    EditorView *ev = (EditorView *)calloc(1, sizeof(EditorView));
    if (!ev) return SOV_ERR_ALLOC;

    ev->hwnd = hwnd;
    ev->caret_visible = true;
    ev->caret_tick = GetTickCount();

    HRESULT hr;
    hr = D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &ev->d2d_factory);
    if (FAILED(hr)) { free(ev); return SOV_ERR_ALLOC; }

    hr = DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED,
        __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown **>(&ev->dw_factory));
    if (FAILED(hr)) { free(ev); return SOV_ERR_ALLOC; }

    hr = ev->dw_factory->CreateTextFormat(
        L"Consolas", nullptr,
        DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL, DWRITE_FONT_STRETCH_NORMAL,
        FONT_SIZE, L"en-us", &ev->text_format);
    if (FAILED(hr)) { free(ev); return SOV_ERR_ALLOC; }

    hr = ev->dw_factory->CreateTextFormat(
        L"Consolas", nullptr,
        DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL, DWRITE_FONT_STRETCH_NORMAL,
        11.0f, L"en-us", &ev->gutter_format);
    if (FAILED(hr)) { free(ev); return SOV_ERR_ALLOC; }
    ev->gutter_format->SetTextAlignment(DWRITE_TEXT_ALIGNMENT_TRAILING);

    RECT rc;
    GetClientRect(hwnd, &rc);
    ev->width  = (uint32_t)(rc.right - rc.left);
    ev->height = (uint32_t)(rc.bottom - rc.top);

    D2D1_RENDER_TARGET_PROPERTIES rtp = D2D1::RenderTargetProperties();
    D2D1_HWND_RENDER_TARGET_PROPERTIES hwp = D2D1::HwndRenderTargetProperties(
        hwnd, D2D1::SizeU(ev->width, ev->height));
    hr = ev->d2d_factory->CreateHwndRenderTarget(rtp, hwp, &ev->rt);
    if (FAILED(hr)) { free(ev); return SOV_ERR_ALLOC; }

    if (FAILED(create_brushes(ev))) { free(ev); return SOV_ERR_ALLOC; }

    *out = ev;
    return SOV_OK;
}

extern "C" void editor_view_destroy(EditorView *ev) {
    if (!ev) return;
    release_brushes(ev);
    if (ev->text_format)   { ev->text_format->Release(); }
    if (ev->gutter_format) { ev->gutter_format->Release(); }
    if (ev->rt)            { ev->rt->Release(); }
    if (ev->d2d_factory)   { ev->d2d_factory->Release(); }
    if (ev->dw_factory)    { ev->dw_factory->Release(); }
    free(ev);
}

extern "C" void editor_view_set_document(EditorView *ev, Document *doc) {
    ev->doc    = doc;
    ev->caret  = 0;
    ev->sel_anchor = 0;
    ev->has_sel    = false;
    ev->scroll_y   = 0.0f;
}

extern "C" void editor_view_set_diagnostics(EditorView *ev, const LspDiagList *list) {
    if (!ev) return;
    if (list) {
        ev->diags    = *list;
        ev->has_diags = (list->count > 0);
    } else {
        ev->has_diags = false;
    }
    InvalidateRect(ev->hwnd, nullptr, FALSE);
}

extern "C" void editor_view_resize(EditorView *ev, uint32_t w, uint32_t h) {
    ev->width  = w;
    ev->height = h;
    if (ev->rt) ev->rt->Resize(D2D1::SizeU(w, h));
}

/* Convert byte offset → (line, col) */
static void offset_to_line_col(Document *doc, size_t offset, size_t *line, size_t *col) {
    char tmp[4096];
    size_t pos = 0;
    *line = 0;
    *col  = 0;
    size_t buf_len = buffer_length(doc->buffer);
    while (pos < offset && pos < buf_len) {
        size_t chunk = offset - pos;
        if (chunk > sizeof(tmp)) chunk = sizeof(tmp);
        size_t n = buffer_read(doc->buffer, pos, tmp, chunk);
        if (n == 0) break;
        for (size_t i = 0; i < n && pos < offset; i++, pos++) {
            if (tmp[i] == '\n') { (*line)++; *col = 0; }
            else                { (*col)++; }
        }
    }
}

/* Render one line of text using DirectWrite */
static void draw_line(EditorView *ev, size_t line_idx, float y,
                      size_t caret_line, size_t sel_start, size_t sel_end, bool has_sel) {
    if (!ev->doc) return;
    float x0 = GUTTER_WIDTH + PADDING_LEFT;
    float view_w = (float)ev->width - x0;
    if (view_w <= 0) return;

    /* Active line highlight */
    if (line_idx == caret_line) {
        D2D1_RECT_F lr = D2D1::RectF(GUTTER_WIDTH, y, (float)ev->width, y + LINE_HEIGHT);
        ev->rt->FillRectangle(lr, ev->br_active_line);
    }

    /* Gutter line number */
    wchar_t num[16];
    swprintf_s(num, 16, L"%zu", line_idx + 1);
    D2D1_RECT_F gr = D2D1::RectF(0, y + 2.0f, GUTTER_WIDTH - 6.0f, y + LINE_HEIGHT);
    ev->rt->DrawText(num, (UINT32)wcslen(num), ev->gutter_format, gr, ev->br_gutter_fg);

    /* Read line text */
    size_t line_start = buffer_line_start(ev->doc->buffer, line_idx);
    size_t line_len   = buffer_line_length(ev->doc->buffer, line_idx);
    if (line_len == 0) return;

    char  utf8[4096];
    size_t n = buffer_read(ev->doc->buffer, line_start, utf8, line_len < 4095 ? line_len : 4095);

    /* UTF-8 → UTF-16 */
    wchar_t wide[4096];
    int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8, (int)n, wide, 4095);
    if (wlen <= 0) return;

    /* Selection highlight */
    if (has_sel && sel_start < line_start + line_len && sel_end > line_start) {
        size_t s = sel_start > line_start ? sel_start - line_start : 0;
        size_t e = sel_end   < line_start + line_len ? sel_end - line_start : line_len;
        IDWriteTextLayout *layout = nullptr;
        ev->dw_factory->CreateTextLayout(wide, (UINT32)wlen,
            ev->text_format, view_w, LINE_HEIGHT, &layout);
        if (layout) {
            DWRITE_HIT_TEST_METRICS m;
            float xs, dummy;
            layout->HitTestTextPosition((UINT32)s, FALSE, &xs, &dummy, &m);
            float xe;
            layout->HitTestTextPosition((UINT32)(e < (size_t)wlen ? e : wlen), FALSE, &xe, &dummy, &m);
            D2D1_RECT_F sr = D2D1::RectF(x0 + xs, y, x0 + xe, y + LINE_HEIGHT);
            ev->rt->FillRectangle(sr, ev->br_sel);
            layout->Release();
        }
    }

    /* Draw text */
    D2D1_RECT_F tr = D2D1::RectF(x0, y, x0 + view_w, y + LINE_HEIGHT);
    ev->rt->DrawText(wide, (UINT32)wlen, ev->text_format, tr, ev->br_text);

    /* LSP squiggles */
    if (ev->has_diags) {
        for (int di = 0; di < ev->diags.count; di++) {
            const LspDiagnostic *d = &ev->diags.entries[di];
            if (d->line != (uint32_t)line_idx) continue;

            ID2D1SolidColorBrush *br = (d->severity == 1) ? ev->br_squiggle_e : ev->br_squiggle_w;

            /* Compute x start from col via layout hit-test */
            float sq_x = x0;
            if (d->col > 0) {
                IDWriteTextLayout *lay = nullptr;
                ev->dw_factory->CreateTextLayout(wide, (UINT32)wlen,
                    ev->text_format, view_w, LINE_HEIGHT, &lay);
                if (lay) {
                    DWRITE_HIT_TEST_METRICS m;
                    float dummy;
                    UINT32 col_clamped = (d->col < (UINT32)wlen) ? d->col : (UINT32)wlen;
                    lay->HitTestTextPosition(col_clamped, FALSE, &sq_x, &dummy, &m);
                    sq_x += x0;
                    lay->Release();
                }
            }

            float sq_y = y + LINE_HEIGHT - 3.0f;
            float sq_end = x0 + view_w;
            float step = 4.0f;
            bool up = true;
            for (float sx = sq_x; sx < sq_end - step; sx += step, up = !up) {
                float sy0 = up ? sq_y      : sq_y + 2.0f;
                float sy1 = up ? sq_y + 2.0f : sq_y;
                ev->rt->DrawLine(D2D1::Point2F(sx, sy0),
                                 D2D1::Point2F(sx + step, sy1), br, 1.2f);
            }
        }
    }
}

extern "C" void editor_view_paint(EditorView *ev, RECT client) {
    if (!ev || !ev->rt) return;

    /* Caret blink */
    DWORD now = GetTickCount();
    if (now - ev->caret_tick > 530) {
        ev->caret_visible = !ev->caret_visible;
        ev->caret_tick = now;
    }

    ev->rt->BeginDraw();
    ev->rt->Clear(&C_BG);

    /* Gutter background */
    D2D1_RECT_F gutter_rect = D2D1::RectF(0, 0, GUTTER_WIDTH, (float)client.bottom);
    ev->rt->FillRectangle(gutter_rect, ev->br_gutter_bg);

    if (!ev->doc) {
        ev->rt->EndDraw(nullptr, nullptr);
        return;
    }

    size_t caret_line, caret_col;
    offset_to_line_col(ev->doc, ev->caret, &caret_line, &caret_col);

    size_t sel_start = ev->has_sel ? (ev->sel_anchor < ev->caret ? ev->sel_anchor : ev->caret) : 0;
    size_t sel_end   = ev->has_sel ? (ev->sel_anchor > ev->caret ? ev->sel_anchor : ev->caret) : 0;

    size_t total_lines = buffer_line_count(ev->doc->buffer);
    size_t first_line  = (size_t)ev->scroll_y;
    size_t visible     = (size_t)((float)ev->height / LINE_HEIGHT) + 2;

    for (size_t i = first_line; i < total_lines && i < first_line + visible; i++) {
        float y = (float)(i - first_line) * LINE_HEIGHT;
        draw_line(ev, i, y, caret_line, sel_start, sel_end, ev->has_sel);
    }

    /* Draw caret */
    if (ev->caret_visible) {
        size_t line_start = buffer_line_start(ev->doc->buffer, caret_line);
        size_t char_in_line = ev->caret - line_start;

        float caret_x = GUTTER_WIDTH + PADDING_LEFT;
        if (char_in_line > 0) {
            char utf8[1024];
            size_t n = buffer_read(ev->doc->buffer, line_start, utf8, char_in_line < 1023 ? char_in_line : 1023);
            wchar_t wide[1024];
            int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8, (int)n, wide, 1023);
            if (wlen > 0) {
                IDWriteTextLayout *layout = nullptr;
                ev->dw_factory->CreateTextLayout(wide, (UINT32)wlen,
                    ev->text_format, 9999.0f, LINE_HEIGHT, &layout);
                if (layout) {
                    DWRITE_TEXT_METRICS tm;
                    layout->GetMetrics(&tm);
                    caret_x += tm.width;
                    layout->Release();
                }
            }
        }
        float caret_y = (float)(caret_line - first_line) * LINE_HEIGHT;
        D2D1_RECT_F cr = D2D1::RectF(caret_x, caret_y + 2.0f, caret_x + CARET_WIDTH, caret_y + LINE_HEIGHT - 2.0f);
        ev->rt->FillRectangle(cr, ev->br_caret);
    }

    HRESULT hr = ev->rt->EndDraw(nullptr, nullptr);
    if (hr == (HRESULT)D2DERR_RECREATE_TARGET) {
        /* Device lost — recreate */
        release_brushes(ev);
        ev->rt->Release(); ev->rt = nullptr;
        RECT rc; GetClientRect(ev->hwnd, &rc);
        D2D1_RENDER_TARGET_PROPERTIES rtp = D2D1::RenderTargetProperties();
        D2D1_HWND_RENDER_TARGET_PROPERTIES hwp = D2D1::HwndRenderTargetProperties(
            ev->hwnd, D2D1::SizeU(rc.right - rc.left, rc.bottom - rc.top));
        ev->d2d_factory->CreateHwndRenderTarget(rtp, hwp, &ev->rt);
        create_brushes(ev);
    }
}

/* Clamp caret into buffer */
static void clamp_caret(EditorView *ev) {
    if (!ev->doc) return;
    size_t len = buffer_length(ev->doc->buffer);
    if (ev->caret > len) ev->caret = len;
}

/* Move caret left/right by one byte (UTF-8 aware would need more work) */
static void caret_move_left(EditorView *ev) {
    if (ev->caret > 0) ev->caret--;
}

static void caret_move_right(EditorView *ev) {
    if (!ev->doc) return;
    if (ev->caret < buffer_length(ev->doc->buffer)) ev->caret++;
}

static void caret_move_up(EditorView *ev) {
    if (!ev->doc) return;
    size_t line, col;
    offset_to_line_col(ev->doc, ev->caret, &line, &col);
    if (line == 0) { ev->caret = 0; return; }
    size_t prev_start = buffer_line_start(ev->doc->buffer, line - 1);
    size_t prev_len   = buffer_line_length(ev->doc->buffer, line - 1);
    ev->caret = prev_start + (col < prev_len ? col : prev_len);
}

static void caret_move_down(EditorView *ev) {
    if (!ev->doc) return;
    size_t line, col;
    offset_to_line_col(ev->doc, ev->caret, &line, &col);
    size_t total = buffer_line_count(ev->doc->buffer);
    if (line + 1 >= total) return;
    size_t next_start = buffer_line_start(ev->doc->buffer, line + 1);
    size_t next_len   = buffer_line_length(ev->doc->buffer, line + 1);
    ev->caret = next_start + (col < next_len ? col : next_len);
}

static void caret_home(EditorView *ev) {
    if (!ev->doc) return;
    size_t line, col; (void)col;
    offset_to_line_col(ev->doc, ev->caret, &line, &col);
    ev->caret = buffer_line_start(ev->doc->buffer, line);
}

static void caret_end(EditorView *ev) {
    if (!ev->doc) return;
    size_t line, col; (void)col;
    offset_to_line_col(ev->doc, ev->caret, &line, &col);
    ev->caret = buffer_line_start(ev->doc->buffer, line)
              + buffer_line_length(ev->doc->buffer, line);
}

static void ensure_caret_visible(EditorView *ev) {
    if (!ev->doc) return;
    size_t line, col; (void)col;
    offset_to_line_col(ev->doc, ev->caret, &line, &col);
    float visible_lines = (float)ev->height / LINE_HEIGHT;
    if ((float)line < ev->scroll_y) {
        ev->scroll_y = (float)line;
    } else if ((float)line >= ev->scroll_y + visible_lines - 1) {
        ev->scroll_y = (float)line - visible_lines + 2.0f;
        if (ev->scroll_y < 0) ev->scroll_y = 0;
    }
}

extern "C" void editor_view_key_down(EditorView *ev, UINT vk, UINT mods) {
    if (!ev->doc) return;

    bool shift = (mods & 1) != 0;
    bool ctrl  = (mods & 2) != 0;

    if (shift && !ev->has_sel) {
        ev->sel_anchor = ev->caret;
        ev->has_sel = true;
    }

    switch (vk) {
    case VK_LEFT:
        if (!shift && ev->has_sel) { ev->caret = ev->sel_anchor < ev->caret ? ev->sel_anchor : ev->caret; ev->has_sel = false; }
        else caret_move_left(ev);
        break;
    case VK_RIGHT:
        if (!shift && ev->has_sel) { ev->caret = ev->sel_anchor > ev->caret ? ev->sel_anchor : ev->caret; ev->has_sel = false; }
        else caret_move_right(ev);
        break;
    case VK_UP:    caret_move_up(ev);   break;
    case VK_DOWN:  caret_move_down(ev); break;
    case VK_HOME:  caret_home(ev); break;
    case VK_END:   caret_end(ev);  break;
    case VK_PRIOR: /* Page Up */
        for (int i = 0; i < 20; i++) caret_move_up(ev);
        break;
    case VK_NEXT:  /* Page Down */
        for (int i = 0; i < 20; i++) caret_move_down(ev);
        break;
    case VK_DELETE: {
        if (ev->has_sel) {
            size_t s = ev->sel_anchor < ev->caret ? ev->sel_anchor : ev->caret;
            size_t e = ev->sel_anchor > ev->caret ? ev->sel_anchor : ev->caret;
            buffer_delete(ev->doc->buffer, s, e - s);
            ev->caret = s; ev->has_sel = false;
        } else {
            buffer_delete(ev->doc->buffer, ev->caret, 1);
        }
        break;
    }
    case VK_BACK: {
        if (ev->has_sel) {
            size_t s = ev->sel_anchor < ev->caret ? ev->sel_anchor : ev->caret;
            size_t e = ev->sel_anchor > ev->caret ? ev->sel_anchor : ev->caret;
            buffer_delete(ev->doc->buffer, s, e - s);
            ev->caret = s; ev->has_sel = false;
        } else if (ev->caret > 0) {
            ev->caret--;
            buffer_delete(ev->doc->buffer, ev->caret, 1);
        }
        break;
    }
    case 'Z':
        if (ctrl) {
            if (buffer_can_undo(ev->doc->buffer)) {
                buffer_undo(ev->doc->buffer);
                clamp_caret(ev);
            }
        }
        break;
    case 'Y':
        if (ctrl) {
            if (buffer_can_redo(ev->doc->buffer)) {
                buffer_redo(ev->doc->buffer);
                clamp_caret(ev);
            }
        }
        break;
    case 'A':
        if (ctrl) {
            ev->sel_anchor = 0;
            ev->caret = buffer_length(ev->doc->buffer);
            ev->has_sel = true;
        }
        break;
    case 'S':
        if (ctrl) document_save(ev->doc);
        break;
    }

    if (!shift) ev->has_sel = false;
    clamp_caret(ev);
    ensure_caret_visible(ev);
    ev->caret_visible = true;
    ev->caret_tick = GetTickCount();

    InvalidateRect(ev->hwnd, NULL, FALSE);
}

extern "C" void editor_view_char(EditorView *ev, wchar_t ch) {
    if (!ev->doc) return;
    if (ch < 0x20 && ch != '\t' && ch != '\n' && ch != '\r') return;
    if (ch == '\r') ch = '\n';

    if (ev->has_sel) {
        size_t s = ev->sel_anchor < ev->caret ? ev->sel_anchor : ev->caret;
        size_t e = ev->sel_anchor > ev->caret ? ev->sel_anchor : ev->caret;
        buffer_delete(ev->doc->buffer, s, e - s);
        ev->caret = s; ev->has_sel = false;
    }

    /* UTF-16 → UTF-8 */
    char utf8[4];
    int utf8_len = WideCharToMultiByte(CP_UTF8, 0, &ch, 1, utf8, 4, NULL, NULL);
    if (utf8_len > 0) {
        buffer_insert(ev->doc->buffer, ev->caret, utf8, (size_t)utf8_len);
        ev->caret += (size_t)utf8_len;
    }

    ensure_caret_visible(ev);
    ev->caret_visible = true;
    ev->caret_tick = GetTickCount();
    InvalidateRect(ev->hwnd, NULL, FALSE);
}

/* Hit test: pixel (x, y) → buffer offset */
static size_t hit_test(EditorView *ev, int px, int py) {
    if (!ev->doc) return 0;

    size_t line = (size_t)(ev->scroll_y + (float)py / LINE_HEIGHT);
    size_t total = buffer_line_count(ev->doc->buffer);
    if (line >= total) line = total - 1;

    size_t line_start = buffer_line_start(ev->doc->buffer, line);
    size_t line_len   = buffer_line_length(ev->doc->buffer, line);
    if (line_len == 0) return line_start;

    float text_x = (float)px - (GUTTER_WIDTH + PADDING_LEFT);
    if (text_x <= 0) return line_start;

    char utf8[4096];
    size_t n = buffer_read(ev->doc->buffer, line_start, utf8, line_len < 4095 ? line_len : 4095);
    wchar_t wide[4096];
    int wlen = MultiByteToWideChar(CP_UTF8, 0, utf8, (int)n, wide, 4095);
    if (wlen <= 0) return line_start;

    IDWriteTextLayout *layout = nullptr;
    ev->dw_factory->CreateTextLayout(wide, (UINT32)wlen,
        ev->text_format, 9999.0f, LINE_HEIGHT, &layout);
    if (!layout) return line_start;

    BOOL trailing, inside;
    DWRITE_HIT_TEST_METRICS m;
    layout->HitTestPoint(text_x, LINE_HEIGHT / 2.0f, &trailing, &inside, &m);
    layout->Release();

    size_t char_pos = m.textPosition + (trailing ? 1 : 0);
    return line_start + (char_pos < line_len ? char_pos : line_len);
}

extern "C" void editor_view_mouse_down(EditorView *ev, int x, int y) {
    ev->caret    = hit_test(ev, x, y);
    ev->sel_anchor = ev->caret;
    ev->has_sel  = false;
    ev->caret_visible = true;
    ev->caret_tick = GetTickCount();
    InvalidateRect(ev->hwnd, NULL, FALSE);
}

extern "C" void editor_view_mouse_move(EditorView *ev, int x, int y, bool btn) {
    if (!btn) return;
    size_t new_pos = hit_test(ev, x, y);
    if (new_pos != ev->caret) {
        ev->caret = new_pos;
        ev->has_sel = (ev->caret != ev->sel_anchor);
        InvalidateRect(ev->hwnd, NULL, FALSE);
    }
}

extern "C" size_t editor_view_caret_offset(const EditorView *ev) {
    return ev->caret;
}

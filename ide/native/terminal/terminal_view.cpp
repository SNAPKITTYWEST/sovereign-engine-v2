/*
 * Sovereign IDE — Terminal View
 * ANSI/VT100 parser + Direct2D renderer on top of the ConPTY backend.
 *
 * Cell grid: TERM_COLS × TERM_ROWS fixed-size character cells.
 * ANSI sequences handled: SGR colours (0-7 fg/bg, bold, reset),
 * cursor motion (CUP/CUU/CUD/CUF/CUB/CHA/VPA/ED/EL/CR/LF/BS),
 * and the scroll region (DECSTBM).
 */

#include <windows.h>
#include <d2d1.h>
#include <dwrite.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <stdint.h>
#include <stdbool.h>

extern "C" {
#include "terminal_view.h"
#include "conpty.h"
}

#define TERM_COLS   220
#define TERM_ROWS   50
#define FONT_SIZE   13.0f

/* ANSI colour palette (dark theme) */
static const D2D1_COLOR_F ANSI_COLORS[8] = {
    { 0.075f, 0.075f, 0.090f, 1.0f }, /* 0 black   → near-black bg  */
    { 0.800f, 0.200f, 0.200f, 1.0f }, /* 1 red                       */
    { 0.180f, 0.700f, 0.290f, 1.0f }, /* 2 green                     */
    { 0.780f, 0.700f, 0.200f, 1.0f }, /* 3 yellow                    */
    { 0.290f, 0.510f, 0.900f, 1.0f }, /* 4 blue                      */
    { 0.700f, 0.290f, 0.800f, 1.0f }, /* 5 magenta                   */
    { 0.200f, 0.700f, 0.780f, 1.0f }, /* 6 cyan                      */
    { 0.820f, 0.820f, 0.820f, 1.0f }, /* 7 white / default fg        */
};
static const D2D1_COLOR_F C_CURSOR = { 0.980f, 0.980f, 0.980f, 0.85f };

/* Terminal cell */
struct Cell {
    wchar_t ch;
    uint8_t fg;   /* 0-7 */
    uint8_t bg;   /* 0-7 */
    bool    bold;
};

/* ANSI escape parser state */
enum ParseState { PS_NORMAL, PS_ESC, PS_CSI };

struct TerminalView {
    HWND   hwnd;
    int    pixel_w, pixel_h;

    ID2D1Factory          *d2d;
    ID2D1HwndRenderTarget *rt;
    IDWriteFactory        *dw;
    IDWriteTextFormat     *fmt;
    IDWriteTextFormat     *fmt_bold;
    ID2D1SolidColorBrush  *brushes[8];   /* ANSI colours */
    ID2D1SolidColorBrush  *br_cursor;

    float cell_w, cell_h;

    Cell     grid[TERM_ROWS][TERM_COLS];
    int      cur_row, cur_col;
    uint8_t  cur_fg, cur_bg;
    bool     cur_bold;
    int      scroll_top, scroll_bot;   /* DECSTBM region, 0-based */

    /* ANSI parser */
    ParseState  ps;
    char        csi_buf[64];
    int         csi_len;

    Terminal   *pty;
    char        read_buf[4096];
};

/* ── helpers ─────────────────────────────────────────────────── */

static void cell_clear(Cell *c, uint8_t bg) {
    c->ch = L' '; c->fg = 7; c->bg = bg; c->bold = false;
}

static void grid_clear(TerminalView *tv) {
    for (int r = 0; r < TERM_ROWS; r++)
        for (int c = 0; c < TERM_COLS; c++)
            cell_clear(&tv->grid[r][c], 0);
}

static void scroll_up(TerminalView *tv, int top, int bot) {
    for (int r = top; r < bot; r++)
        memcpy(tv->grid[r], tv->grid[r+1], sizeof(tv->grid[0]));
    for (int c = 0; c < TERM_COLS; c++)
        cell_clear(&tv->grid[bot][c], tv->cur_bg);
}

static void newline(TerminalView *tv) {
    tv->cur_col = 0;
    if (tv->cur_row < tv->scroll_bot)
        tv->cur_row++;
    else
        scroll_up(tv, tv->scroll_top, tv->scroll_bot);
}

static void put_char(TerminalView *tv, wchar_t ch) {
    if (tv->cur_col >= TERM_COLS) {
        tv->cur_col = 0;
        if (tv->cur_row < tv->scroll_bot) tv->cur_row++;
        else scroll_up(tv, tv->scroll_top, tv->scroll_bot);
    }
    Cell *c = &tv->grid[tv->cur_row][tv->cur_col];
    c->ch = ch; c->fg = tv->cur_fg; c->bg = tv->cur_bg; c->bold = tv->cur_bold;
    tv->cur_col++;
}

/* Parse a single CSI param (1-based default d) */
static int csi_param(const char *buf, int idx, int def) {
    /* buf is semicolon-separated params, e.g. "2;31" */
    const char *p = buf;
    for (int i = 0; i < idx; i++) {
        p = strchr(p, ';');
        if (!p) return def;
        p++;
    }
    if (*p == '\0' || *p == ';') return def;
    return atoi(p);
}

static void apply_sgr(TerminalView *tv, const char *params) {
    /* Walk semicolon-delimited numbers */
    char tmp[64];
    strncpy_s(tmp, 64, params, 63);
    char *tok = tmp;
    char *next;
    do {
        next = strchr(tok, ';');
        if (next) *next = '\0';
        int n = (*tok == '\0') ? 0 : atoi(tok);
        if (n == 0)  { tv->cur_fg = 7; tv->cur_bg = 0; tv->cur_bold = false; }
        else if (n == 1) tv->cur_bold = true;
        else if (n == 22) tv->cur_bold = false;
        else if (n >= 30 && n <= 37) tv->cur_fg = (uint8_t)(n - 30);
        else if (n == 39) tv->cur_fg = 7;
        else if (n >= 40 && n <= 47) tv->cur_bg = (uint8_t)(n - 40);
        else if (n == 49) tv->cur_bg = 0;
        /* bright variants */
        else if (n >= 90 && n <= 97) tv->cur_fg = (uint8_t)(n - 90);
        else if (n >= 100 && n <= 107) tv->cur_bg = (uint8_t)(n - 100);
        if (next) tok = next + 1;
    } while (next);
}

static void dispatch_csi(TerminalView *tv) {
    char *buf = tv->csi_buf;
    int   len = tv->csi_len;
    if (len == 0) return;

    char final = buf[len - 1];
    buf[len - 1] = '\0';          /* null-terminate params portion */
    const char *params = buf;

    int p1 = csi_param(params, 0, 1);
    int p2 = csi_param(params, 1, 1);

    switch (final) {
    case 'A': /* CUU */ tv->cur_row = (tv->cur_row - p1 < 0) ? 0 : tv->cur_row - p1; break;
    case 'B': /* CUD */ tv->cur_row = (tv->cur_row + p1 >= TERM_ROWS) ? TERM_ROWS-1 : tv->cur_row + p1; break;
    case 'C': /* CUF */ tv->cur_col = (tv->cur_col + p1 >= TERM_COLS) ? TERM_COLS-1 : tv->cur_col + p1; break;
    case 'D': /* CUB */ tv->cur_col = (tv->cur_col - p1 < 0) ? 0 : tv->cur_col - p1; break;
    case 'H': /* CUP */ case 'f':
        tv->cur_row = (p1 < 1 ? 1 : p1) - 1;
        tv->cur_col = (p2 < 1 ? 1 : p2) - 1;
        if (tv->cur_row >= TERM_ROWS) tv->cur_row = TERM_ROWS - 1;
        if (tv->cur_col >= TERM_COLS) tv->cur_col = TERM_COLS - 1;
        break;
    case 'G': /* CHA */ tv->cur_col = (p1 < 1 ? 1 : p1) - 1; break;
    case 'd': /* VPA */ tv->cur_row = (p1 < 1 ? 1 : p1) - 1; break;
    case 'J': /* ED  */
        if (p1 == 2 || p1 == 3) grid_clear(tv);
        else if (p1 == 0) {
            for (int c = tv->cur_col; c < TERM_COLS; c++)
                cell_clear(&tv->grid[tv->cur_row][c], tv->cur_bg);
            for (int r = tv->cur_row+1; r < TERM_ROWS; r++)
                for (int c = 0; c < TERM_COLS; c++)
                    cell_clear(&tv->grid[r][c], tv->cur_bg);
        }
        break;
    case 'K': /* EL  */
        if (p1 == 0)
            for (int c = tv->cur_col; c < TERM_COLS; c++)
                cell_clear(&tv->grid[tv->cur_row][c], tv->cur_bg);
        else if (p1 == 1)
            for (int c = 0; c <= tv->cur_col; c++)
                cell_clear(&tv->grid[tv->cur_row][c], tv->cur_bg);
        else
            for (int c = 0; c < TERM_COLS; c++)
                cell_clear(&tv->grid[tv->cur_row][c], tv->cur_bg);
        break;
    case 'r': /* DECSTBM */
        tv->scroll_top = (p1 < 1 ? 1 : p1) - 1;
        tv->scroll_bot = (p2 < 1 ? TERM_ROWS : p2) - 1;
        if (tv->scroll_top >= TERM_ROWS) tv->scroll_top = 0;
        if (tv->scroll_bot >= TERM_ROWS) tv->scroll_bot = TERM_ROWS - 1;
        break;
    case 'm': /* SGR */
        apply_sgr(tv, params);
        break;
    default: break;
    }
}

static void feed_byte(TerminalView *tv, char byte) {
    switch (tv->ps) {
    case PS_NORMAL:
        if (byte == '\x1b') { tv->ps = PS_ESC; return; }
        if (byte == '\r')   { tv->cur_col = 0; return; }
        if (byte == '\n')   { newline(tv); return; }
        if (byte == '\b')   { if (tv->cur_col > 0) tv->cur_col--; return; }
        if (byte == '\t') {
            tv->cur_col = (tv->cur_col + 8) & ~7;
            if (tv->cur_col >= TERM_COLS) tv->cur_col = TERM_COLS - 1;
            return;
        }
        if ((unsigned char)byte >= 0x20) {
            /* UTF-8 single-byte only for now; multibyte → replacement char */
            put_char(tv, (wchar_t)(unsigned char)byte);
        }
        break;

    case PS_ESC:
        if (byte == '[') { tv->ps = PS_CSI; tv->csi_len = 0; return; }
        if (byte == 'c') { grid_clear(tv); tv->cur_row = 0; tv->cur_col = 0; }
        tv->ps = PS_NORMAL;
        break;

    case PS_CSI:
        if (tv->csi_len < 63)
            tv->csi_buf[tv->csi_len++] = byte;
        /* Final byte is in range 0x40–0x7E */
        if (byte >= 0x40 && byte <= 0x7E) {
            tv->csi_buf[tv->csi_len] = '\0';
            dispatch_csi(tv);
            tv->ps = PS_NORMAL;
            tv->csi_len = 0;
        }
        break;
    }
}

static void feed_bytes(TerminalView *tv, const char *data, size_t len) {
    for (size_t i = 0; i < len; i++)
        feed_byte(tv, data[i]);
}

/* ── D2D init / destroy ──────────────────────────────────────── */

static HRESULT init_d2d(TerminalView *tv) {
    HRESULT hr = D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &tv->d2d);
    if (FAILED(hr)) return hr;

    hr = DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown **>(&tv->dw));
    if (FAILED(hr)) return hr;

    tv->dw->CreateTextFormat(L"Consolas", nullptr,
        DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL,
        DWRITE_FONT_STRETCH_NORMAL, FONT_SIZE, L"en-us", &tv->fmt);
    tv->dw->CreateTextFormat(L"Consolas", nullptr,
        DWRITE_FONT_WEIGHT_BOLD, DWRITE_FONT_STYLE_NORMAL,
        DWRITE_FONT_STRETCH_NORMAL, FONT_SIZE, L"en-us", &tv->fmt_bold);

    /* Measure one cell */
    IDWriteTextLayout *tl = nullptr;
    tv->dw->CreateTextLayout(L"M", 1, tv->fmt, 1000.0f, 1000.0f, &tl);
    if (tl) {
        DWRITE_TEXT_METRICS m; tl->GetMetrics(&m);
        tv->cell_w = m.width; tv->cell_h = m.height + 2.0f;
        tl->Release();
    } else {
        tv->cell_w = 8.0f; tv->cell_h = 16.0f;
    }

    RECT rc; GetClientRect(tv->hwnd, &rc);
    tv->d2d->CreateHwndRenderTarget(
        D2D1::RenderTargetProperties(),
        D2D1::HwndRenderTargetProperties(tv->hwnd,
            D2D1::SizeU(rc.right - rc.left, rc.bottom - rc.top)),
        &tv->rt);

    if (tv->rt) {
        for (int i = 0; i < 8; i++)
            tv->rt->CreateSolidColorBrush(ANSI_COLORS[i], &tv->brushes[i]);
        tv->rt->CreateSolidColorBrush(C_CURSOR, &tv->br_cursor);
    }
    return S_OK;
}

/* ── Public API ──────────────────────────────────────────────── */

extern "C" SovResult terminal_view_create(TerminalView **out, HWND hwnd) {
    TerminalView *tv = (TerminalView *)calloc(1, sizeof(TerminalView));
    if (!tv) return SOV_ERR_ALLOC;

    tv->hwnd       = hwnd;
    tv->cur_fg     = 7;
    tv->cur_bg     = 0;
    tv->scroll_top = 0;
    tv->scroll_bot = TERM_ROWS - 1;

    grid_clear(tv);

    init_d2d(tv); /* best-effort — rt may be null on failure, paint checks */

    /* Compute initial cols/rows from pixel size */
    RECT rc; GetClientRect(hwnd, &rc);
    tv->pixel_w = rc.right  - rc.left;
    tv->pixel_h = rc.bottom - rc.top;

    uint16_t cols = (tv->cell_w > 0) ? (uint16_t)(tv->pixel_w / tv->cell_w) : 80;
    uint16_t rows = (tv->cell_h > 0) ? (uint16_t)(tv->pixel_h / tv->cell_h) : 24;
    if (cols < 10) cols = 80;
    if (rows < 4)  rows = 24;

    /* Best-effort: ConPTY may not be available on older Windows */
    SovResult r = terminal_create(&tv->pty, cols, rows);
    if (r != SOV_OK) {
        /* Fall back to a "no pty" display — still renders */
        tv->pty = nullptr;
        const char *msg = "Terminal unavailable (requires Windows 10 1809+)\r\n";
        feed_bytes(tv, msg, strlen(msg));
    } else {
        const char *banner = "\x1b[32mSovereign IDE Terminal\x1b[0m\r\n";
        feed_bytes(tv, banner, strlen(banner));
    }

    *out = tv;
    return SOV_OK;
}

extern "C" void terminal_view_destroy(TerminalView *tv) {
    if (!tv) return;
    if (tv->pty) terminal_destroy(tv->pty);
    if (tv->br_cursor) tv->br_cursor->Release();
    for (int i = 0; i < 8; i++) if (tv->brushes[i]) tv->brushes[i]->Release();
    if (tv->fmt)      tv->fmt->Release();
    if (tv->fmt_bold) tv->fmt_bold->Release();
    if (tv->rt)       tv->rt->Release();
    if (tv->d2d)      tv->d2d->Release();
    if (tv->dw)       tv->dw->Release();
    free(tv);
}

extern "C" void terminal_view_resize(TerminalView *tv, int w, int h) {
    tv->pixel_w = w; tv->pixel_h = h;
    if (tv->rt) tv->rt->Resize(D2D1::SizeU((UINT32)w, (UINT32)h));
    if (tv->pty && tv->cell_w > 0 && tv->cell_h > 0) {
        uint16_t cols = (uint16_t)(w / tv->cell_w);
        uint16_t rows = (uint16_t)(h / tv->cell_h);
        if (cols < 10) cols = 80;
        if (rows < 4)  rows = 24;
        terminal_resize(tv->pty, cols, rows);
    }
}

extern "C" void terminal_view_tick(TerminalView *tv) {
    if (!tv->pty) return;
    size_t nread = 0;
    if (terminal_read(tv->pty, tv->read_buf, sizeof(tv->read_buf), &nread) == SOV_OK && nread > 0) {
        feed_bytes(tv, tv->read_buf, nread);
        InvalidateRect(tv->hwnd, NULL, FALSE);
    }
}

extern "C" void terminal_view_key_down(TerminalView *tv, UINT vk, UINT mods) {
    if (!tv->pty) return;
    char seq[8] = {0};
    int  slen   = 0;
    bool ctrl   = (mods & 2) != 0;

    switch (vk) {
    case VK_RETURN: seq[0] = '\r'; slen = 1; break;
    case VK_BACK:   seq[0] = '\x7f'; slen = 1; break;
    case VK_TAB:    seq[0] = '\t'; slen = 1; break;
    case VK_ESCAPE: seq[0] = '\x1b'; slen = 1; break;
    case VK_UP:     seq[0]='\x1b';seq[1]='[';seq[2]='A'; slen=3; break;
    case VK_DOWN:   seq[0]='\x1b';seq[1]='[';seq[2]='B'; slen=3; break;
    case VK_RIGHT:  seq[0]='\x1b';seq[1]='[';seq[2]='C'; slen=3; break;
    case VK_LEFT:   seq[0]='\x1b';seq[1]='[';seq[2]='D'; slen=3; break;
    case VK_HOME:   seq[0]='\x1b';seq[1]='[';seq[2]='H'; slen=3; break;
    case VK_END:    seq[0]='\x1b';seq[1]='[';seq[2]='F'; slen=3; break;
    case VK_DELETE: seq[0]='\x1b';seq[1]='[';seq[2]='3';seq[3]='~'; slen=4; break;
    default:
        if (ctrl && vk >= 'A' && vk <= 'Z') {
            seq[0] = (char)(vk - 'A' + 1); slen = 1;
        }
        break;
    }
    if (slen > 0) terminal_write(tv->pty, seq, (size_t)slen);
}

extern "C" void terminal_view_char(TerminalView *tv, wchar_t ch) {
    if (!tv->pty) return;
    if (ch < 0x20 || ch == 0x7F) return;  /* handled by key_down */
    /* Convert to UTF-8 */
    char utf8[4];
    int  ulen = 0;
    if (ch < 0x80) {
        utf8[0] = (char)ch; ulen = 1;
    } else if (ch < 0x800) {
        utf8[0] = (char)(0xC0 | (ch >> 6));
        utf8[1] = (char)(0x80 | (ch & 0x3F));
        ulen = 2;
    } else {
        utf8[0] = (char)(0xE0 | (ch >> 12));
        utf8[1] = (char)(0x80 | ((ch >> 6) & 0x3F));
        utf8[2] = (char)(0x80 | (ch & 0x3F));
        ulen = 3;
    }
    terminal_write(tv->pty, utf8, (size_t)ulen);
}

extern "C" void terminal_view_paint(TerminalView *tv) {
    if (!tv->rt && tv->d2d) {
        RECT rc; GetClientRect(tv->hwnd, &rc);
        UINT W = rc.right  > rc.left ? (UINT)(rc.right  - rc.left) : 1;
        UINT H = rc.bottom > rc.top  ? (UINT)(rc.bottom - rc.top)  : 1;
        tv->d2d->CreateHwndRenderTarget(D2D1::RenderTargetProperties(),
            D2D1::HwndRenderTargetProperties(tv->hwnd, D2D1::SizeU(W, H)), &tv->rt);
        if (tv->rt) {
            for (int i = 0; i < 8; i++)
                tv->rt->CreateSolidColorBrush(ANSI_COLORS[i], &tv->brushes[i]);
            tv->rt->CreateSolidColorBrush(C_CURSOR, &tv->br_cursor);
        }
    }
    if (!tv->rt) return;
    tv->rt->BeginDraw();
    tv->rt->Clear(&ANSI_COLORS[0]);

    int visible_rows = (tv->cell_h > 0) ? (int)(tv->pixel_h / tv->cell_h) + 1 : TERM_ROWS;
    int visible_cols = (tv->cell_w > 0) ? (int)(tv->pixel_w / tv->cell_w) + 1 : TERM_COLS;
    if (visible_rows > TERM_ROWS) visible_rows = TERM_ROWS;
    if (visible_cols > TERM_COLS) visible_cols = TERM_COLS;

    for (int r = 0; r < visible_rows; r++) {
        for (int c = 0; c < visible_cols; c++) {
            Cell *cell = &tv->grid[r][c];
            float x = c * tv->cell_w;
            float y = r * tv->cell_h;
            D2D1_RECT_F cr = D2D1::RectF(x, y, x + tv->cell_w, y + tv->cell_h);

            /* Background — only draw if non-default */
            if (cell->bg != 0) {
                tv->rt->FillRectangle(cr, tv->brushes[cell->bg & 7]);
            }

            /* Character */
            if (cell->ch != L' ' && cell->ch != L'\0') {
                auto *fmt = cell->bold ? tv->fmt_bold : tv->fmt;
                tv->rt->DrawText(&cell->ch, 1, fmt, cr, tv->brushes[cell->fg & 7]);
            }
        }
    }

    /* Cursor block */
    {
        float cx = tv->cur_col * tv->cell_w;
        float cy = tv->cur_row * tv->cell_h;
        D2D1_RECT_F cur_r = D2D1::RectF(cx, cy, cx + tv->cell_w, cy + tv->cell_h);
        tv->rt->FillRectangle(cur_r, tv->br_cursor);
        /* Redraw char under cursor inverted */
        Cell *cc = &tv->grid[tv->cur_row][tv->cur_col];
        if (cc->ch != L' ' && cc->ch != L'\0') {
            auto *fmt = cc->bold ? tv->fmt_bold : tv->fmt;
            tv->rt->DrawText(&cc->ch, 1, fmt, cur_r, tv->brushes[0]);
        }
    }

    HRESULT hr = tv->rt->EndDraw(nullptr, nullptr);
    if (hr == (HRESULT)D2DERR_RECREATE_TARGET) {
        tv->rt->Release(); tv->rt = nullptr;
        RECT rc; GetClientRect(tv->hwnd, &rc);
        tv->d2d->CreateHwndRenderTarget(
            D2D1::RenderTargetProperties(),
            D2D1::HwndRenderTargetProperties(tv->hwnd,
                D2D1::SizeU(rc.right - rc.left, rc.bottom - rc.top)),
            &tv->rt);
        if (tv->rt) {
            for (int i = 0; i < 8; i++)
                tv->rt->CreateSolidColorBrush(ANSI_COLORS[i], &tv->brushes[i]);
            tv->rt->CreateSolidColorBrush(C_CURSOR, &tv->br_cursor);
        }
    }
}

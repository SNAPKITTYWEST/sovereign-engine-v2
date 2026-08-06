/*
 * Sovereign IDE — Win32 Window
 * Main window proc. Owns editor view lifecycle, keyboard, mouse, paint.
 */

#include "window.h"
#include "application.h"
#include "../../core/events.h"
#include "../../editor/editor_view.h"
#include "../../editor/document.h"

#define WINDOW_CLASS_NAME L"SovereignIDE"
#define WINDOW_TITLE      L"Sovereign IDE"

static EditorView *g_editor_view = NULL;
static Document    g_doc;

static LRESULT CALLBACK window_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {

    case WM_CREATE: {
        document_new(&g_doc);
        buffer_insert(g_doc.buffer, 0,
            "// Sovereign IDE\n// Type here to start editing.\n\nint main(void) {\n    return 0;\n}\n",
            81);
        buffer_mark_clean(g_doc.buffer);

        if (editor_view_create(&g_editor_view, hwnd) == SOV_OK) {
            editor_view_set_document(g_editor_view, &g_doc);
        }

        /* 530ms timer for caret blink */
        SetTimer(hwnd, 1, 530, NULL);
        return 0;
    }

    case WM_TIMER:
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;

    case WM_PAINT: {
        PAINTSTRUCT ps;
        BeginPaint(hwnd, &ps);
        if (g_editor_view) {
            RECT rc;
            GetClientRect(hwnd, &rc);
            editor_view_paint(g_editor_view, rc);
        }
        EndPaint(hwnd, &ps);
        return 0;
    }

    case WM_SIZE: {
        uint32_t w = LOWORD(lp);
        uint32_t h = HIWORD(lp);
        if (g_editor_view) editor_view_resize(g_editor_view, w, h);
        Event ev = { .kind = EVENT_RESIZE };
        ev.resize.width = w; ev.resize.height = h;
        event_post(ev);
        return 0;
    }

    case WM_KEYDOWN:
    case WM_SYSKEYDOWN: {
        if (g_editor_view) {
            UINT mods = 0;
            if (GetKeyState(VK_SHIFT)   & 0x8000) mods |= 1;
            if (GetKeyState(VK_CONTROL) & 0x8000) mods |= 2;
            if (GetKeyState(VK_MENU)    & 0x8000) mods |= 4;
            editor_view_key_down(g_editor_view, (UINT)wp, mods);
        }
        return 0;
    }

    case WM_CHAR: {
        if (g_editor_view) {
            editor_view_char(g_editor_view, (wchar_t)wp);
        }
        return 0;
    }

    case WM_LBUTTONDOWN: {
        SetCapture(hwnd);
        if (g_editor_view) {
            editor_view_mouse_down(g_editor_view,
                (int)(short)LOWORD(lp), (int)(short)HIWORD(lp));
        }
        return 0;
    }

    case WM_LBUTTONUP:
        ReleaseCapture();
        return 0;

    case WM_MOUSEMOVE: {
        if (g_editor_view) {
            bool btn = (wp & MK_LBUTTON) != 0;
            editor_view_mouse_move(g_editor_view,
                (int)(short)LOWORD(lp), (int)(short)HIWORD(lp), btn);
        }
        return 0;
    }

    case WM_MOUSEWHEEL: {
        if (g_editor_view) {
            int delta = GET_WHEEL_DELTA_WPARAM(wp);
            /* Forward as key events for scroll */
            UINT vk = (delta > 0) ? VK_UP : VK_DOWN;
            for (int i = 0; i < SCROLL_LINES; i++) {
                event_post((Event){ .kind = EVENT_MOUSE_WHEEL });
            }
            (void)vk;
        }
        return 0;
    }

    case WM_SETFOCUS:
        event_post((Event){ .kind = EVENT_FOCUS_GAINED });
        return 0;

    case WM_KILLFOCUS:
        event_post((Event){ .kind = EVENT_FOCUS_LOST });
        return 0;

    case WM_DPICHANGED: {
        RECT *r = (RECT *)lp;
        SetWindowPos(hwnd, NULL, r->left, r->top,
                     r->right - r->left, r->bottom - r->top,
                     SWP_NOZORDER | SWP_NOACTIVATE);
        return 0;
    }

    case WM_CLOSE:
        KillTimer(hwnd, 1);
        if (g_editor_view) { editor_view_destroy(g_editor_view); g_editor_view = NULL; }
        document_destroy(&g_doc);
        event_post((Event){ .kind = EVENT_QUIT });
        app_request_quit();
        return 0;

    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }

    return DefWindowProcW(hwnd, msg, wp, lp);
}

HWND window_create(int width, int height) {
    WNDCLASSEXW wc = {0};
    wc.cbSize        = sizeof(wc);
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = window_proc;
    wc.hInstance     = app_get_hinstance();
    wc.hCursor       = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszClassName = WINDOW_CLASS_NAME;
    RegisterClassExW(&wc);

    HWND hwnd = CreateWindowExW(
        0,
        WINDOW_CLASS_NAME,
        WINDOW_TITLE,
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT,
        width, height,
        NULL, NULL,
        app_get_hinstance(),
        NULL
    );

    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    return hwnd;
}

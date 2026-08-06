/*
 * Sovereign IDE — Application Shell
 * Top-level window + child panel HWNDs + layout engine.
 * This replaces window.c as the orchestrator.
 */

#include "shell.h"
#include "application.h"
#include "../../ui/layout.h"
#include "../../ui/project_tree.h"
#include "../../ui/status_bar.h"
#include "../../ui/output_panel.h"
#include "../../editor/editor_view.h"
#include "../../editor/document.h"
#include "../../terminal/terminal_view.h"
#include "../../git/repository.h"
#include "../../build/cmake_runner.h"
#include "../../lsp/client.h"
#include "../../core/events.h"
#include <commdlg.h>
#include <shlobj.h>

#define TIMER_CARET  1
#define TIMER_PTY    2
#define TIMER_GIT    3

/* Child window IDs */
#define IDC_SIDEBAR   101
#define IDC_EDITOR    102
#define IDC_BOTTOM    103
#define IDC_STATUSBAR 104

#define SHELL_CLASS   L"SovShell"
#define PANEL_CLASS   L"SovPanel"
#define SHELL_TITLE   L"Sovereign IDE"

static struct {
    HWND frame;
    HWND wnd_sidebar;
    HWND wnd_editor;
    HWND wnd_bottom;    /* container only — no D2D on this one */
    HWND wnd_output;    /* OutputPanel lives here */
    HWND wnd_terminal;  /* TerminalView lives here */
    HWND wnd_status;

    Layout        layout;
    ProjectTree  *tree;
    EditorView   *editor;
    OutputPanel  *output;
    TerminalView *terminal;
    StatusBar    *status;

    GitRepo       git;
    CmakeRunner  *builder;
    LspClient    *lsp;
    int           lsp_version;

    Document      doc;
    int           client_w;
    int           client_h;
    bool          terminal_focused;
} g_shell;

/* -----------------------------------------------------------
 * Build runner callbacks
 * ----------------------------------------------------------- */
static void on_build_line(const char *text, bool is_err, void *ctx) {
    (void)ctx; (void)is_err;
    if (!g_shell.output) return;
    /* Convert UTF-8 line to wide */
    wchar_t wbuf[2048];
    MultiByteToWideChar(CP_UTF8, 0, text, -1, wbuf, 2048);
    output_panel_append(g_shell.output, wbuf);
    output_panel_append(g_shell.output, L"\n");
    /* Show output panel while building */
    g_shell.terminal_focused = false;
    ShowWindow(g_shell.wnd_output,   SW_SHOW);
    ShowWindow(g_shell.wnd_terminal, SW_HIDE);
}

static void on_build_done(int exit_code, void *ctx) {
    (void)ctx;
    if (!g_shell.output) return;
    wchar_t msg[64];
    if (exit_code == 0)
        swprintf_s(msg, 64, L"✔ Build succeeded\n");
    else
        swprintf_s(msg, 64, L"✘ Build failed (exit %d)\n", exit_code);
    output_panel_append(g_shell.output, msg);
    if (g_shell.status)
        status_bar_set_message(g_shell.status,
            exit_code == 0 ? L"Build OK" : L"Build FAILED");
    InvalidateRect(g_shell.wnd_bottom,  NULL, FALSE);
    InvalidateRect(g_shell.wnd_status,  NULL, FALSE);
}

/* -----------------------------------------------------------
 * LSP diagnostics callback
 * ----------------------------------------------------------- */
static void on_lsp_diag(const LspDiagList *list, void *ctx) {
    (void)ctx;
    if (!g_shell.editor) return;
    /* Only apply diags that match the current open file */
    if (g_shell.doc.has_path &&
        _wcsicmp(list->uri, g_shell.doc.path) == 0)
    {
        editor_view_set_diagnostics(g_shell.editor, list);
    }
}

/* -----------------------------------------------------------
 * File open callback (from project tree click)
 * ----------------------------------------------------------- */
static void on_open_file(const wchar_t *path, void *ctx) {
    (void)ctx;
    document_destroy(&g_shell.doc);
    if (document_open(&g_shell.doc, path) == SOV_OK) {
        editor_view_set_document(g_shell.editor, &g_shell.doc);
        editor_view_set_diagnostics(g_shell.editor, NULL);

        /* Notify LSP of the new file */
        if (g_shell.lsp) {
            char utf8[1 << 20];
            size_t blen = buffer_length(g_shell.doc.buffer);
            if (blen > sizeof(utf8) - 1) blen = sizeof(utf8) - 1;
            buffer_read(g_shell.doc.buffer, 0, utf8, blen);
            utf8[blen] = '\0';
            g_shell.lsp_version = 1;
            lsp_client_open(g_shell.lsp, path, utf8, blen);
        }

        /* extract filename for status bar */
        const wchar_t *name = wcsrchr(path, L'\\');
        status_bar_set_file(g_shell.status, name ? name + 1 : path, false);

        output_panel_append(g_shell.output, L"Opened: ");
        output_panel_append(g_shell.output, path);
        output_panel_append(g_shell.output, L"\n");
    } else {
        output_panel_append(g_shell.output, L"Failed to open file\n");
    }
    InvalidateRect(g_shell.wnd_editor, NULL, FALSE);
}

/* -----------------------------------------------------------
 * Reposition all child windows from layout
 * ----------------------------------------------------------- */
static void apply_layout(void) {
    PanelRect rects[PANEL_COUNT];
    layout_compute(&g_shell.layout, g_shell.client_w, g_shell.client_h, rects);

    SetWindowPos(g_shell.wnd_sidebar, NULL,
        rects[PANEL_SIDEBAR].x, rects[PANEL_SIDEBAR].y,
        rects[PANEL_SIDEBAR].w, rects[PANEL_SIDEBAR].h,
        SWP_NOZORDER | SWP_NOACTIVATE);

    SetWindowPos(g_shell.wnd_editor, NULL,
        rects[PANEL_EDITOR].x, rects[PANEL_EDITOR].y,
        rects[PANEL_EDITOR].w, rects[PANEL_EDITOR].h,
        SWP_NOZORDER | SWP_NOACTIVATE);

    SetWindowPos(g_shell.wnd_bottom, NULL,
        rects[PANEL_BOTTOM].x, rects[PANEL_BOTTOM].y,
        rects[PANEL_BOTTOM].w, rects[PANEL_BOTTOM].h,
        SWP_NOZORDER | SWP_NOACTIVATE);

    SetWindowPos(g_shell.wnd_status, NULL,
        rects[PANEL_STATUSBAR].x, rects[PANEL_STATUSBAR].y,
        rects[PANEL_STATUSBAR].w, rects[PANEL_STATUSBAR].h,
        SWP_NOZORDER | SWP_NOACTIVATE);

    if (g_shell.editor)
        editor_view_resize(g_shell.editor,
            (uint32_t)rects[PANEL_EDITOR].w, (uint32_t)rects[PANEL_EDITOR].h);
    if (g_shell.tree)
        project_tree_resize(g_shell.tree,
            rects[PANEL_SIDEBAR].w, rects[PANEL_SIDEBAR].h);
    /* Resize output+terminal sub-windows to fill wnd_bottom */
    if (g_shell.wnd_output)
        SetWindowPos(g_shell.wnd_output, NULL, 0, 0,
            rects[PANEL_BOTTOM].w, rects[PANEL_BOTTOM].h, SWP_NOZORDER | SWP_NOACTIVATE);
    if (g_shell.wnd_terminal)
        SetWindowPos(g_shell.wnd_terminal, NULL, 0, 0,
            rects[PANEL_BOTTOM].w, rects[PANEL_BOTTOM].h, SWP_NOZORDER | SWP_NOACTIVATE);
    if (g_shell.output)
        output_panel_resize(g_shell.output,
            rects[PANEL_BOTTOM].w, rects[PANEL_BOTTOM].h);
    if (g_shell.terminal)
        terminal_view_resize(g_shell.terminal,
            rects[PANEL_BOTTOM].w, rects[PANEL_BOTTOM].h);
    if (g_shell.status)
        status_bar_resize(g_shell.status,
            rects[PANEL_STATUSBAR].w, rects[PANEL_STATUSBAR].h);
}

/* -----------------------------------------------------------
 * Panel child window proc (sidebar / editor / bottom / status)
 * ----------------------------------------------------------- */
static LRESULT CALLBACK panel_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        BeginPaint(hwnd, &ps);
        if (hwnd == g_shell.wnd_sidebar && g_shell.tree)
            project_tree_paint(g_shell.tree);
        else if (hwnd == g_shell.wnd_editor && g_shell.editor) {
            RECT rc; GetClientRect(hwnd, &rc);
            editor_view_paint(g_shell.editor, rc);
        }
        else if (hwnd == g_shell.wnd_output && g_shell.output)
            output_panel_paint(g_shell.output);
        else if (hwnd == g_shell.wnd_terminal && g_shell.terminal)
            terminal_view_paint(g_shell.terminal);
        else if (hwnd == g_shell.wnd_status && g_shell.status)
            status_bar_paint(g_shell.status);
        EndPaint(hwnd, &ps);
        return 0;
    }

    case WM_LBUTTONDOWN: {
        int x = (int)(short)LOWORD(lp), y = (int)(short)HIWORD(lp);
        if (hwnd == g_shell.wnd_sidebar && g_shell.tree)
            project_tree_mouse_down(g_shell.tree, x, y);
        else if (hwnd == g_shell.wnd_editor && g_shell.editor) {
            SetFocus(hwnd);
            g_shell.terminal_focused = false;
            editor_view_mouse_down(g_shell.editor, x, y);
        }
        else if (hwnd == g_shell.wnd_terminal || hwnd == g_shell.wnd_output) {
            SetFocus(hwnd);
            g_shell.terminal_focused = (hwnd == g_shell.wnd_terminal);
        }
        return 0;
    }

    case WM_MOUSEMOVE: {
        if (hwnd == g_shell.wnd_editor && g_shell.editor) {
            bool btn = (wp & MK_LBUTTON) != 0;
            editor_view_mouse_move(g_shell.editor,
                (int)(short)LOWORD(lp), (int)(short)HIWORD(lp), btn);
        }
        return 0;
    }

    case WM_KEYDOWN:
    case WM_SYSKEYDOWN: {
        if (hwnd == g_shell.wnd_terminal && g_shell.terminal) {
            UINT mods = 0;
            if (GetKeyState(VK_CONTROL) & 0x8000) mods |= 2;
            terminal_view_key_down(g_shell.terminal, (UINT)wp, mods);
            return 0;
        }
        if (hwnd == g_shell.wnd_editor && g_shell.editor) {
            UINT mods = 0;
            if (GetKeyState(VK_SHIFT)   & 0x8000) mods |= 1;
            if (GetKeyState(VK_CONTROL) & 0x8000) mods |= 2;
            if (GetKeyState(VK_MENU)    & 0x8000) mods |= 4;
            editor_view_key_down(g_shell.editor, (UINT)wp, mods);

            /* Update status bar line/col after navigation */
            if (g_shell.status && g_shell.doc.buffer) {
                size_t off = editor_view_caret_offset(g_shell.editor);
                char tmp[1];
                /* count lines up to offset */
                size_t line = 1, col = 1;
                for (size_t i = 0; i < off; i++) {
                    size_t n = buffer_read(g_shell.doc.buffer, i, tmp, 1);
                    if (n && tmp[0] == '\n') { line++; col = 1; } else col++;
                }
                status_bar_set_pos(g_shell.status, (int)line, (int)col);
                status_bar_set_file(g_shell.status,
                    g_shell.doc.has_path ? wcsrchr(g_shell.doc.path, L'\\') + 1 : L"untitled",
                    document_is_dirty(&g_shell.doc));
            }
        } else if (hwnd == g_shell.wnd_sidebar && g_shell.tree) {
            project_tree_key_down(g_shell.tree, (UINT)wp);
        }
        return 0;
    }

    case WM_CHAR: {
        if (hwnd == g_shell.wnd_terminal && g_shell.terminal) {
            terminal_view_char(g_shell.terminal, (wchar_t)wp);
        } else if (hwnd == g_shell.wnd_editor && g_shell.editor) {
            editor_view_char(g_shell.editor, (wchar_t)wp);
            /* Notify LSP of change */
            if (g_shell.lsp && g_shell.doc.has_path && g_shell.doc.buffer) {
                char utf8[1 << 20];
                size_t blen = buffer_length(g_shell.doc.buffer);
                if (blen < sizeof(utf8)) {
                    buffer_read(g_shell.doc.buffer, 0, utf8, blen);
                    utf8[blen] = '\0';
                    lsp_client_change(g_shell.lsp, g_shell.doc.path,
                                      utf8, blen, ++g_shell.lsp_version);
                }
            }
        }
        return 0;
    }

    case WM_MOUSEWHEEL: {
        if (hwnd == g_shell.wnd_bottom && g_shell.output)
            output_panel_scroll(g_shell.output, GET_WHEEL_DELTA_WPARAM(wp) / 40);
        return 0;
    }

    case WM_TIMER:
        if (wp == TIMER_PTY && hwnd == g_shell.wnd_terminal) {
            terminal_view_tick(g_shell.terminal);
            InvalidateRect(g_shell.wnd_terminal, NULL, FALSE);
        } else {
            InvalidateRect(hwnd, NULL, FALSE);
        }
        return 0;
    }

    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* -----------------------------------------------------------
 * Frame window proc (top-level)
 * ----------------------------------------------------------- */
static LRESULT CALLBACK shell_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {

    case WM_CREATE: {
        layout_init(&g_shell.layout);

        /* Measure initial client area so D2D render targets get real dimensions */
        RECT cr;
        GetClientRect(hwnd, &cr);
        g_shell.client_w = cr.right  - cr.left;
        g_shell.client_h = cr.bottom - cr.top;
        if (g_shell.client_w < 1) g_shell.client_w = 1280;
        if (g_shell.client_h < 1) g_shell.client_h = 800;

        /* Compute layout so child panels get non-zero sizes */
        PanelRect rects[PANEL_COUNT];
        layout_compute(&g_shell.layout, g_shell.client_w, g_shell.client_h, rects);

        /* Create child panels at their real positions */
        HINSTANCE hi = app_get_hinstance();
        g_shell.wnd_sidebar  = CreateWindowExW(0, PANEL_CLASS, NULL,
            WS_CHILD | WS_VISIBLE,
            rects[PANEL_SIDEBAR].x,  rects[PANEL_SIDEBAR].y,
            rects[PANEL_SIDEBAR].w,  rects[PANEL_SIDEBAR].h,
            hwnd, (HMENU)IDC_SIDEBAR, hi, NULL);
        g_shell.wnd_editor   = CreateWindowExW(0, PANEL_CLASS, NULL,
            WS_CHILD | WS_VISIBLE,
            rects[PANEL_EDITOR].x,   rects[PANEL_EDITOR].y,
            rects[PANEL_EDITOR].w,   rects[PANEL_EDITOR].h,
            hwnd, (HMENU)IDC_EDITOR,  hi, NULL);
        g_shell.wnd_bottom   = CreateWindowExW(0, PANEL_CLASS, NULL,
            WS_CHILD | WS_VISIBLE,
            rects[PANEL_BOTTOM].x,   rects[PANEL_BOTTOM].y,
            rects[PANEL_BOTTOM].w,   rects[PANEL_BOTTOM].h,
            hwnd, (HMENU)IDC_BOTTOM,  hi, NULL);
        g_shell.wnd_status   = CreateWindowExW(0, PANEL_CLASS, NULL,
            WS_CHILD | WS_VISIBLE,
            rects[PANEL_STATUSBAR].x, rects[PANEL_STATUSBAR].y,
            rects[PANEL_STATUSBAR].w, rects[PANEL_STATUSBAR].h,
            hwnd, (HMENU)IDC_STATUSBAR, hi, NULL);

        /* Output and terminal need separate HWNDs (each owns one D2D RT) */
        int bw = rects[PANEL_BOTTOM].w;
        int bh = rects[PANEL_BOTTOM].h;
        g_shell.wnd_output   = CreateWindowExW(0, PANEL_CLASS, NULL,
            WS_CHILD | WS_VISIBLE, 0, 0, bw, bh,
            g_shell.wnd_bottom, NULL, hi, NULL);
        g_shell.wnd_terminal = CreateWindowExW(0, PANEL_CLASS, NULL,
            WS_CHILD, 0, 0, bw, bh,
            g_shell.wnd_bottom, NULL, hi, NULL);

        /* Init subsystems — each on its own HWND */
        #define DBGINIT(call, name) do { \
            SovResult _r = (call); \
            if (_r != SOV_OK) MessageBoxW(NULL, L##name L" FAILED", L"Init Error", MB_OK); \
        } while(0)
        project_tree_create(&g_shell.tree, g_shell.wnd_sidebar);
        editor_view_create(&g_shell.editor, g_shell.wnd_editor);
        output_panel_create(&g_shell.output, g_shell.wnd_output);
        terminal_view_create(&g_shell.terminal, g_shell.wnd_terminal);
        status_bar_create(&g_shell.status, g_shell.wnd_status);
        #undef DBGINIT
        g_shell.terminal_focused = false;  /* default: show output panel */
        /* wnd_output visible, wnd_terminal hidden until user toggles */
        ShowWindow(g_shell.wnd_output,   SW_SHOW);
        ShowWindow(g_shell.wnd_terminal, SW_HIDE);

        /* Wire callbacks */
        if (g_shell.tree) {
            project_tree_set_callback(g_shell.tree, on_open_file, NULL);
        }

        /* Default document */
        document_new(&g_shell.doc);
        buffer_insert(g_shell.doc.buffer, 0,
            "#include <stdio.h>\n\nint main(void) {\n    printf(\"Sovereign IDE\\n\");\n    return 0;\n}\n",
            88);
        buffer_mark_clean(g_shell.doc.buffer);
        if (g_shell.editor)
            editor_view_set_document(g_shell.editor, &g_shell.doc);

        /* Open current working directory in project tree */
        wchar_t cwd[MAX_PATH];
        GetCurrentDirectoryW(MAX_PATH, cwd);
        if (g_shell.tree)
            project_tree_open(g_shell.tree, cwd);

        if (g_shell.status) {
            status_bar_set_file(g_shell.status, L"main.c", false);
            status_bar_set_pos(g_shell.status, 1, 1);
            status_bar_set_branch(g_shell.status, L"master");
            status_bar_set_message(g_shell.status, L"GCC 13.2");
        }

        /* Output welcome */
        if (g_shell.output) {
            output_panel_append(g_shell.output, L"Sovereign IDE ready.\n");
            output_panel_append(g_shell.output, L"Project: ");
            output_panel_append(g_shell.output, cwd);
            output_panel_append(g_shell.output, L"\n");
        }

        /* Git branch detection */
        if (git_repo_open(&g_shell.git, cwd) == SOV_OK && g_shell.status) {
            wchar_t branch_disp[136];
            swprintf_s(branch_disp, 136, L"%s%s",
                g_shell.git.detached ? L"detached:" : L"",
                g_shell.git.branch);
            status_bar_set_branch(g_shell.status, branch_disp);
        }

        /* CMake build runner */
        wchar_t build_dir[MAX_PATH];
        swprintf_s(build_dir, MAX_PATH, L"%s\\build", cwd);
        cmake_runner_create(&g_shell.builder, build_dir,
                            on_build_line, on_build_done, NULL);

        /* Start LSP server (clangd must be on PATH) */
        g_shell.lsp = NULL;
        g_shell.lsp_version = 1;
        if (lsp_client_start(&g_shell.lsp, L"clangd",
                             on_lsp_diag, NULL) == SOV_OK) {
            lsp_client_initialize(g_shell.lsp, cwd);
            output_panel_append(g_shell.output, L"LSP: clangd started.\n");
        } else {
            output_panel_append(g_shell.output, L"LSP: clangd not found — install LLVM.\n");
            g_shell.lsp = NULL;
        }

        SetTimer(g_shell.wnd_editor,   TIMER_CARET, 530, NULL);
        SetTimer(g_shell.wnd_terminal, TIMER_PTY,   16,  NULL);  /* ~60fps PTY poll */
        SetTimer(hwnd, TIMER_GIT, 3000, NULL);                /* git refresh every 3s */
        return 0;
    }

    case WM_SIZE: {
        g_shell.client_w = (int)(short)LOWORD(lp);
        g_shell.client_h = (int)(short)HIWORD(lp);
        apply_layout();
        return 0;
    }

    case WM_MOUSEMOVE: {
        int mx = (int)(short)LOWORD(lp);
        int my = (int)(short)HIWORD(lp);
        if (g_shell.layout.dragging) {
            layout_update_drag(&g_shell.layout, mx, my);
            apply_layout();
            return 0;
        }
        int spl = layout_hit_splitter(&g_shell.layout, g_shell.client_w, g_shell.client_h, mx, my);
        if (spl == 0 || spl == 1)
            SetCursor(LoadCursorW(NULL, (LPCWSTR)IDC_SIZEWE));
        else if (spl == 2)
            SetCursor(LoadCursorW(NULL, (LPCWSTR)IDC_SIZENS));
        else
            SetCursor(LoadCursorW(NULL, (LPCWSTR)IDC_ARROW));
        return 0;
    }

    case WM_LBUTTONDOWN: {
        int mx = (int)(short)LOWORD(lp);
        int my = (int)(short)HIWORD(lp);
        int spl = layout_hit_splitter(&g_shell.layout, g_shell.client_w, g_shell.client_h, mx, my);
        if (spl >= 0) {
            layout_begin_drag(&g_shell.layout, spl, mx, my);
            SetCapture(hwnd);
        }
        return 0;
    }

    case WM_LBUTTONUP:
        layout_end_drag(&g_shell.layout);
        ReleaseCapture();
        return 0;

    case WM_COMMAND: {
        switch (LOWORD(wp)) {
        case 1001: /* File > Open Folder */
        {
            /* Use SHBrowseForFolder for folder selection */
            BROWSEINFOW bi = {0};
            bi.hwndOwner = hwnd;
            bi.lpszTitle = L"Open Project Folder";
            bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
            LPITEMIDLIST pidl = SHBrowseForFolderW(&bi);
            if (pidl) {
                wchar_t path[MAX_PATH];
                SHGetPathFromIDListW(pidl, path);
                CoTaskMemFree(pidl);
                if (g_shell.tree) project_tree_open(g_shell.tree, path);
                output_panel_append(g_shell.output, L"Opened folder: ");
                output_panel_append(g_shell.output, path);
                output_panel_append(g_shell.output, L"\n");
            }
            break;
        }
        case 1002: /* File > Open File */
        {
            OPENFILENAMEW ofn = {0};
            wchar_t file[MAX_PATH] = {0};
            ofn.lStructSize = sizeof(ofn);
            ofn.hwndOwner   = hwnd;
            ofn.lpstrFile   = file;
            ofn.nMaxFile    = MAX_PATH;
            ofn.lpstrFilter = L"C/C++ Files\0*.c;*.cpp;*.h;*.hpp\0All Files\0*.*\0";
            ofn.Flags       = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST;
            if (GetOpenFileNameW(&ofn)) {
                on_open_file(file, NULL);
            }
            break;
        }
        case 1003: /* File > Save */
            if (g_shell.doc.has_path) {
                document_save(&g_shell.doc);
                output_panel_append(g_shell.output, L"Saved.\n");
            }
            break;
        case 1010: /* View > Toggle Sidebar */
            g_shell.layout.sidebar_visible = !g_shell.layout.sidebar_visible;
            apply_layout();
            break;
        case 1011: /* View > Toggle Bottom */
            g_shell.layout.bottom_visible = !g_shell.layout.bottom_visible;
            apply_layout();
            break;
        case 1020: /* Run > Build (Ctrl+B) */
            if (g_shell.builder && !cmake_runner_is_running(g_shell.builder)) {
                output_panel_clear(g_shell.output);
                output_panel_append(g_shell.output, L"Building...\n");
                g_shell.terminal_focused = false;
                ShowWindow(g_shell.wnd_output,   SW_SHOW);
                ShowWindow(g_shell.wnd_terminal, SW_HIDE);
                if (cmake_runner_build(g_shell.builder) != SOV_OK)
                    output_panel_append(g_shell.output, L"cmake not found — is it on PATH?\n");
            }
            break;
        case 1021: /* View > Toggle Terminal/Output */
            g_shell.terminal_focused = !g_shell.terminal_focused;
            ShowWindow(g_shell.wnd_output,   g_shell.terminal_focused ? SW_HIDE : SW_SHOW);
            ShowWindow(g_shell.wnd_terminal, g_shell.terminal_focused ? SW_SHOW : SW_HIDE);
            break;
        case 9999: /* File > Exit */
            PostMessageW(hwnd, WM_CLOSE, 0, 0);
            break;
        }
        return 0;
    }

    case WM_TIMER: {
        if (wp == TIMER_GIT) {
            if (git_repo_refresh(&g_shell.git) == SOV_OK && g_shell.status) {
                wchar_t branch_disp[136];
                swprintf_s(branch_disp, 136, L"%s%s",
                    g_shell.git.detached ? L"detached:" : L"",
                    g_shell.git.branch);
                status_bar_set_branch(g_shell.status, branch_disp);
                InvalidateRect(g_shell.wnd_status, NULL, FALSE);
            }
            if (g_shell.builder) cmake_runner_tick(g_shell.builder);
            if (g_shell.lsp)     lsp_client_tick(g_shell.lsp);
        }
        return 0;
    }

    case WM_DPICHANGED: {
        RECT *r = (RECT *)lp;
        SetWindowPos(hwnd, NULL, r->left, r->top,
                     r->right - r->left, r->bottom - r->top,
                     SWP_NOZORDER | SWP_NOACTIVATE);
        return 0;
    }

    case WM_CLOSE:
        KillTimer(hwnd, TIMER_GIT);
        KillTimer(g_shell.wnd_editor,   TIMER_CARET);
        KillTimer(g_shell.wnd_terminal, TIMER_PTY);
        if (g_shell.lsp)      { lsp_client_shutdown(g_shell.lsp);          g_shell.lsp      = NULL; }
        if (g_shell.builder)  { cmake_runner_destroy(g_shell.builder);    g_shell.builder  = NULL; }
        if (g_shell.editor)   { editor_view_destroy(g_shell.editor);      g_shell.editor   = NULL; }
        if (g_shell.tree)     { project_tree_destroy(g_shell.tree);        g_shell.tree     = NULL; }
        if (g_shell.terminal) { terminal_view_destroy(g_shell.terminal);   g_shell.terminal = NULL; }
        if (g_shell.output)   { output_panel_destroy(g_shell.output);      g_shell.output   = NULL; }
        if (g_shell.status)   { status_bar_destroy(g_shell.status);        g_shell.status   = NULL; }
        document_destroy(&g_shell.doc);
        DestroyWindow(hwnd);
        return 0;

    case WM_DESTROY:
        app_request_quit();
        PostQuitMessage(0);
        return 0;
    }

    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* Build the native menu */
static void build_menu(HWND hwnd) {
    HMENU bar  = CreateMenu();
    HMENU file = CreatePopupMenu();
    HMENU view = CreatePopupMenu();
    HMENU run  = CreatePopupMenu();

    AppendMenuW(file, MF_STRING, 1001, L"Open &Folder…\tCtrl+Shift+O");
    AppendMenuW(file, MF_STRING, 1002, L"Open &File…\tCtrl+O");
    AppendMenuW(file, MF_SEPARATOR, 0, NULL);
    AppendMenuW(file, MF_STRING, 1003, L"&Save\tCtrl+S");
    AppendMenuW(file, MF_SEPARATOR, 0, NULL);
    AppendMenuW(file, MF_STRING, 9999, L"E&xit");

    AppendMenuW(view, MF_STRING, 1010, L"Toggle &Sidebar\tCtrl+\\");
    AppendMenuW(view, MF_STRING, 1011, L"Toggle &Output\tCtrl+J");
    AppendMenuW(view, MF_STRING, 1021, L"Toggle &Terminal\tCtrl+`");

    AppendMenuW(run,  MF_STRING, 1020, L"&Build\tCtrl+B");

    AppendMenuW(bar, MF_POPUP, (UINT_PTR)file, L"&File");
    AppendMenuW(bar, MF_POPUP, (UINT_PTR)view, L"&View");
    AppendMenuW(bar, MF_POPUP, (UINT_PTR)run,  L"&Run");
    SetMenu(hwnd, bar);
}

SovResult shell_create(HINSTANCE hinstance, int width, int height) {
    /* Register panel class */
    WNDCLASSEXW pc = {0};
    pc.cbSize        = sizeof(pc);
    pc.style         = CS_HREDRAW | CS_VREDRAW;
    pc.lpfnWndProc   = panel_proc;
    pc.hInstance     = hinstance;
    pc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    pc.lpszClassName = PANEL_CLASS;
    RegisterClassExW(&pc);

    /* Register shell class */
    WNDCLASSEXW sc = {0};
    sc.cbSize        = sizeof(sc);
    sc.style         = CS_HREDRAW | CS_VREDRAW;
    sc.lpfnWndProc   = shell_proc;
    sc.hInstance     = hinstance;
    sc.hCursor       = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    sc.hbrBackground = (HBRUSH)GetStockObject(BLACK_BRUSH);
    sc.lpszClassName = SHELL_CLASS;
    RegisterClassExW(&sc);

    g_shell.frame = CreateWindowExW(
        0, SHELL_CLASS, SHELL_TITLE,
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, width, height,
        NULL, NULL, hinstance, NULL
    );

    if (!g_shell.frame) return SOV_ERR_IO;

    build_menu(g_shell.frame);
    ShowWindow(g_shell.frame, SW_SHOW);
    UpdateWindow(g_shell.frame);
    return SOV_OK;
}

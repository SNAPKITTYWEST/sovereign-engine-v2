/*
 * Sovereign IDE — Project Tree
 * Recursive directory listing, expand/collapse, file open callback.
 */

#include <windows.h>
#include <d2d1.h>
#include <dwrite.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

/* Full struct definition lives here — COM types kept out of the C-visible header */
#define TREE_MAX_NODES 8192
#define TREE_ROW_H     20
#define TREE_INDENT    16

typedef enum TreeNodeKind {
    TNODE_DIR  = 0,
    TNODE_FILE = 1,
} TreeNodeKind;

typedef struct TreeNode {
    wchar_t      name[MAX_PATH];
    wchar_t      full_path[MAX_PATH];
    TreeNodeKind kind;
    int          depth;
    int          parent;
    bool         expanded;
    bool         visible;
} TreeNode;

struct ProjectTree {
    TreeNode nodes[TREE_MAX_NODES];
    int      count;
    int      selected;
    int      scroll_top;
    wchar_t  root_path[MAX_PATH];

    ID2D1Factory          *d2d_factory;
    ID2D1HwndRenderTarget *rt;
    IDWriteFactory        *dw_factory;
    IDWriteTextFormat     *text_fmt;
    ID2D1SolidColorBrush  *br_bg;
    ID2D1SolidColorBrush  *br_sel;
    ID2D1SolidColorBrush  *br_text;
    ID2D1SolidColorBrush  *br_dir;
    HWND                   hwnd;

    void (*on_open_file)(const wchar_t *path, void *ctx);
    void *on_open_ctx;
};

extern "C" {
#include "project_tree.h"
}

static const D2D1_COLOR_F C_BG    = { 0.098f, 0.098f, 0.118f, 1.0f };
static const D2D1_COLOR_F C_SEL   = { 0.173f, 0.369f, 0.529f, 0.8f };
static const D2D1_COLOR_F C_TEXT  = { 0.800f, 0.800f, 0.820f, 1.0f };
static const D2D1_COLOR_F C_DIR   = { 0.659f, 0.820f, 1.000f, 1.0f };

static HRESULT init_d2d(ProjectTree *pt) {
    HRESULT hr = D2D1CreateFactory(D2D1_FACTORY_TYPE_SINGLE_THREADED, &pt->d2d_factory);
    if (FAILED(hr)) return hr;
    hr = DWriteCreateFactory(DWRITE_FACTORY_TYPE_SHARED, __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown**>(&pt->dw_factory));
    if (FAILED(hr)) return hr;
    hr = pt->dw_factory->CreateTextFormat(L"Segoe UI", nullptr,
        DWRITE_FONT_WEIGHT_NORMAL, DWRITE_FONT_STYLE_NORMAL, DWRITE_FONT_STRETCH_NORMAL,
        12.0f, L"en-us", &pt->text_fmt);
    if (FAILED(hr)) return hr;
    pt->text_fmt->SetWordWrapping(DWRITE_WORD_WRAPPING_NO_WRAP);

    RECT rc; GetClientRect(pt->hwnd, &rc);
    D2D1_HWND_RENDER_TARGET_PROPERTIES hwp = D2D1::HwndRenderTargetProperties(
        pt->hwnd, D2D1::SizeU(rc.right - rc.left, rc.bottom - rc.top));
    hr = pt->d2d_factory->CreateHwndRenderTarget(D2D1::RenderTargetProperties(), hwp, &pt->rt);
    if (FAILED(hr)) return hr;

    if (pt->rt) {
        pt->rt->CreateSolidColorBrush(C_BG,   &pt->br_bg);
        pt->rt->CreateSolidColorBrush(C_SEL,  &pt->br_sel);
        pt->rt->CreateSolidColorBrush(C_TEXT, &pt->br_text);
        pt->rt->CreateSolidColorBrush(C_DIR,  &pt->br_dir);
    }
    return S_OK;
}

extern "C" SovResult project_tree_create(ProjectTree **out, HWND hwnd) {
    ProjectTree *pt = (ProjectTree *)calloc(1, sizeof(ProjectTree));
    if (!pt) return SOV_ERR_ALLOC;
    pt->hwnd = hwnd;
    pt->selected = -1;
    init_d2d(pt); /* best-effort — rt may be null on failure, paint checks */
    *out = pt;
    return SOV_OK;
}

extern "C" void project_tree_destroy(ProjectTree *pt) {
    if (!pt) return;
    if (pt->br_bg)   pt->br_bg->Release();
    if (pt->br_sel)  pt->br_sel->Release();
    if (pt->br_text) pt->br_text->Release();
    if (pt->br_dir)  pt->br_dir->Release();
    if (pt->text_fmt)    pt->text_fmt->Release();
    if (pt->rt)          pt->rt->Release();
    if (pt->d2d_factory) pt->d2d_factory->Release();
    if (pt->dw_factory)  pt->dw_factory->Release();
    free(pt);
}

/* Add a node. Returns the index. */
static int add_node(ProjectTree *pt, const wchar_t *name, const wchar_t *full_path,
                    TreeNodeKind kind, int depth, int parent) {
    if (pt->count >= TREE_MAX_NODES) return -1;
    int idx = pt->count++;
    TreeNode *n = &pt->nodes[idx];
    wcscpy_s(n->name, MAX_PATH, name);
    wcscpy_s(n->full_path, MAX_PATH, full_path);
    n->kind     = kind;
    n->depth    = depth;
    n->parent   = parent;
    n->expanded = false;
    n->visible  = true;
    return idx;
}

/* Sort: dirs first, then files, both alphabetical (case-insensitive) */
static int cmp_entries(const void *a, const void *b) {
    const WIN32_FIND_DATAW *fa = (const WIN32_FIND_DATAW *)a;
    const WIN32_FIND_DATAW *fb = (const WIN32_FIND_DATAW *)b;
    bool da = (fa->dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
    bool db = (fb->dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
    if (da && !db) return -1;
    if (!da && db) return  1;
    return _wcsicmp(fa->cFileName, fb->cFileName);
}

static void scan_dir(ProjectTree *pt, const wchar_t *dir_path, int depth, int parent) {
    wchar_t pattern[MAX_PATH];
    swprintf_s(pattern, MAX_PATH, L"%s\\*", dir_path);

    WIN32_FIND_DATAW entries[4096];
    int entry_count = 0;

    HANDLE h = FindFirstFileW(pattern, &entries[0]);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (wcscmp(entries[entry_count].cFileName, L".") == 0) continue;
        if (wcscmp(entries[entry_count].cFileName, L"..") == 0) continue;
        /* skip hidden */
        if (entries[entry_count].dwFileAttributes & FILE_ATTRIBUTE_HIDDEN) continue;
        if (entry_count < 4095) entry_count++;
    } while (FindNextFileW(h, &entries[entry_count]));
    FindClose(h);

    qsort(entries, (size_t)entry_count, sizeof(WIN32_FIND_DATAW), cmp_entries);

    for (int i = 0; i < entry_count; i++) {
        wchar_t full[MAX_PATH];
        swprintf_s(full, MAX_PATH, L"%s\\%s", dir_path, entries[i].cFileName);
        bool is_dir = (entries[i].dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        add_node(pt, entries[i].cFileName, full,
                 is_dir ? TNODE_DIR : TNODE_FILE, depth, parent);
    }
}

static void expand_node(ProjectTree *pt, int idx) {
    TreeNode *n = &pt->nodes[idx];
    if (n->kind != TNODE_DIR || n->expanded) return;
    n->expanded = true;

    /* insert children after idx, shift existing */
    int insert_at = idx + 1;
    /* first count existing children already present (re-expand) */
    /* for simplicity: children were never added yet if first expand */
    /* scan directory and insert nodes at insert_at */
    int before = pt->count;
    scan_dir(pt, n->full_path, n->depth + 1, idx);
    int added = pt->count - before;

    /* move newly appended nodes to insert_at */
    if (added > 0 && insert_at < before) {
        TreeNode tmp[TREE_MAX_NODES];
        memcpy(tmp, &pt->nodes[insert_at], (size_t)(before - insert_at) * sizeof(TreeNode));
        memcpy(&pt->nodes[insert_at], &pt->nodes[before], (size_t)added * sizeof(TreeNode));
        memcpy(&pt->nodes[insert_at + added], tmp, (size_t)(before - insert_at) * sizeof(TreeNode));
    }
}

static void collapse_node(ProjectTree *pt, int idx) {
    TreeNode *n = &pt->nodes[idx];
    if (!n->expanded) return;
    n->expanded = false;

    /* remove all descendants */
    int i = idx + 1;
    while (i < pt->count) {
        if (pt->nodes[i].depth > n->depth) {
            memmove(&pt->nodes[i], &pt->nodes[i+1],
                    (size_t)(pt->count - i - 1) * sizeof(TreeNode));
            pt->count--;
        } else {
            break;
        }
    }
}

extern "C" SovResult project_tree_open(ProjectTree *pt, const wchar_t *path) {
    pt->count = 0;
    pt->selected = -1;
    pt->scroll_top = 0;
    wcscpy_s(pt->root_path, MAX_PATH, path);

    /* Root node */
    wchar_t *name = (wchar_t *)wcsrchr(path, L'\\');
    if (!name) name = (wchar_t *)path;
    else name++;

    int root = add_node(pt, name, path, TNODE_DIR, 0, -1);
    expand_node(pt, root);
    return SOV_OK;
}

extern "C" void project_tree_resize(ProjectTree *pt, int w, int h) {
    if (pt->rt) pt->rt->Resize(D2D1::SizeU((UINT32)w, (UINT32)h));
}

extern "C" void project_tree_paint(ProjectTree *pt) {
    if (!pt->rt && pt->d2d_factory) {
        RECT rc; GetClientRect(pt->hwnd, &rc);
        UINT W = rc.right  > rc.left ? (UINT)(rc.right  - rc.left) : 1;
        UINT H = rc.bottom > rc.top  ? (UINT)(rc.bottom - rc.top)  : 1;
        pt->d2d_factory->CreateHwndRenderTarget(D2D1::RenderTargetProperties(),
            D2D1::HwndRenderTargetProperties(pt->hwnd, D2D1::SizeU(W, H)), &pt->rt);
        if (pt->rt) {
            pt->rt->CreateSolidColorBrush(C_BG,   &pt->br_bg);
            pt->rt->CreateSolidColorBrush(C_SEL,  &pt->br_sel);
            pt->rt->CreateSolidColorBrush(C_TEXT, &pt->br_text);
            pt->rt->CreateSolidColorBrush(C_DIR,  &pt->br_dir);
        }
    }
    if (!pt->rt) return;
    pt->rt->BeginDraw();
    pt->rt->Clear(&C_BG);

    RECT rc; GetClientRect(pt->hwnd, &rc);
    int visible_rows = (rc.bottom - rc.top) / TREE_ROW_H + 1;

    int row = 0;
    for (int i = 0; i < pt->count; i++) {
        TreeNode *n = &pt->nodes[i];
        if (!n->visible) continue;

        if (row < pt->scroll_top) { row++; continue; }
        if (row >= pt->scroll_top + visible_rows) break;

        float y = (float)((row - pt->scroll_top) * TREE_ROW_H);
        float x = (float)(n->depth * TREE_INDENT + 4);

        /* Selection highlight */
        if (i == pt->selected) {
            D2D1_RECT_F sr = D2D1::RectF(0, y, (float)rc.right, y + TREE_ROW_H);
            pt->rt->FillRectangle(sr, pt->br_sel);
        }

        /* Expand arrow for dirs */
        if (n->kind == TNODE_DIR) {
            wchar_t arrow = n->expanded ? L'\x25BC' : L'\x25B6';
            D2D1_RECT_F ar = D2D1::RectF(x, y + 2.0f, x + 14.0f, y + (float)TREE_ROW_H);
            pt->rt->DrawText(&arrow, 1, pt->text_fmt, ar, pt->br_dir);
            x += 14.0f;
        } else {
            x += 14.0f;
        }

        /* Name */
        D2D1_RECT_F tr = D2D1::RectF(x, y + 2.0f, (float)rc.right - 4.0f, y + (float)TREE_ROW_H);
        auto *br = (n->kind == TNODE_DIR) ? pt->br_dir : pt->br_text;
        pt->rt->DrawText(n->name, (UINT32)wcslen(n->name), pt->text_fmt, tr, br);

        row++;
    }

    HRESULT hr = pt->rt->EndDraw(nullptr, nullptr);
    if (hr == (HRESULT)D2DERR_RECREATE_TARGET) {
        /* recreate on device loss */
        pt->rt->Release(); pt->rt = nullptr;
        RECT r; GetClientRect(pt->hwnd, &r);
        pt->d2d_factory->CreateHwndRenderTarget(
            D2D1::RenderTargetProperties(),
            D2D1::HwndRenderTargetProperties(pt->hwnd,
                D2D1::SizeU(r.right - r.left, r.bottom - r.top)),
            &pt->rt);
    }
}

extern "C" void project_tree_mouse_down(ProjectTree *pt, int x, int y) {
    (void)x;
    int row = pt->scroll_top + y / TREE_ROW_H;
    int visible_idx = 0;
    for (int i = 0; i < pt->count; i++) {
        if (!pt->nodes[i].visible) continue;
        if (visible_idx == row) {
            if (pt->selected == i && pt->nodes[i].kind == TNODE_FILE) {
                /* double-click would open; single click selects */
            }
            pt->selected = i;

            if (pt->nodes[i].kind == TNODE_DIR) {
                if (pt->nodes[i].expanded) collapse_node(pt, i);
                else                       expand_node(pt, i);
            } else {
                if (pt->on_open_file) {
                    pt->on_open_file(pt->nodes[i].full_path, pt->on_open_ctx);
                }
            }
            InvalidateRect(pt->hwnd, NULL, FALSE);
            return;
        }
        visible_idx++;
    }
}

extern "C" void project_tree_set_callback(ProjectTree *pt,
        void (*on_open)(const wchar_t *path, void *ctx), void *ctx) {
    pt->on_open_file = on_open;
    pt->on_open_ctx  = ctx;
}

extern "C" void project_tree_key_down(ProjectTree *pt, UINT vk) {
    if (pt->selected < 0) { pt->selected = 0; return; }
    switch (vk) {
    case VK_UP:
        if (pt->selected > 0) pt->selected--;
        break;
    case VK_DOWN:
        if (pt->selected < pt->count - 1) pt->selected++;
        break;
    case VK_RIGHT:
        if (pt->nodes[pt->selected].kind == TNODE_DIR)
            expand_node(pt, pt->selected);
        break;
    case VK_LEFT:
        if (pt->nodes[pt->selected].kind == TNODE_DIR)
            collapse_node(pt, pt->selected);
        break;
    case VK_RETURN:
        if (pt->nodes[pt->selected].kind == TNODE_FILE && pt->on_open_file)
            pt->on_open_file(pt->nodes[pt->selected].full_path, pt->on_open_ctx);
        break;
    }
    InvalidateRect(pt->hwnd, NULL, FALSE);
}

/*
 * Sovereign IDE — Layout Engine
 * Computes pixel rects for all panels from sidebar_w, chat_w, bottom_h.
 * No recursion — straightforward arithmetic.
 */

#include "layout.h"
#include <string.h>

void layout_init(Layout *l) {
    memset(l, 0, sizeof(*l));
    l->sidebar_w      = SIDEBAR_DEFAULT_W;
    l->chat_w         = CHAT_DEFAULT_W;
    l->bottom_h       = BOTTOM_DEFAULT_H;
    l->sidebar_visible = true;
    l->chat_visible    = true;
    l->bottom_visible  = true;
}

void layout_compute(const Layout *l, int W, int H, PanelRect rects[PANEL_COUNT]) {
    int status_h = STATUSBAR_H;
    int usable_h = H - status_h;          /* above status bar */

    int left_x  = l->sidebar_visible ? l->sidebar_w + SPLITTER_THICK : 0;
    int right_x  = W - (l->chat_visible ? l->chat_w + SPLITTER_THICK : 0);
    int center_w = right_x - left_x;
    if (center_w < 0) center_w = 0;

    int bottom_h_actual = l->bottom_visible ? l->bottom_h + SPLITTER_THICK : 0;
    int editor_h = usable_h - bottom_h_actual;
    if (editor_h < 40) editor_h = 40;

    /* Sidebar */
    rects[PANEL_SIDEBAR].x = 0;
    rects[PANEL_SIDEBAR].y = 0;
    rects[PANEL_SIDEBAR].w = l->sidebar_visible ? l->sidebar_w : 0;
    rects[PANEL_SIDEBAR].h = usable_h;

    /* Editor */
    rects[PANEL_EDITOR].x = left_x;
    rects[PANEL_EDITOR].y = 0;
    rects[PANEL_EDITOR].w = center_w;
    rects[PANEL_EDITOR].h = editor_h;

    /* Bottom panel */
    rects[PANEL_BOTTOM].x = left_x;
    rects[PANEL_BOTTOM].y = editor_h + (l->bottom_visible ? SPLITTER_THICK : 0);
    rects[PANEL_BOTTOM].w = center_w;
    rects[PANEL_BOTTOM].h = l->bottom_visible ? l->bottom_h : 0;

    /* Chat panel */
    rects[PANEL_CHAT].x = right_x + (l->chat_visible ? SPLITTER_THICK : 0) - (l->chat_visible ? 0 : SPLITTER_THICK);
    rects[PANEL_CHAT].x = l->chat_visible ? (W - l->chat_w) : W;
    rects[PANEL_CHAT].y = 0;
    rects[PANEL_CHAT].w = l->chat_visible ? l->chat_w : 0;
    rects[PANEL_CHAT].h = usable_h;

    /* Status bar */
    rects[PANEL_STATUSBAR].x = 0;
    rects[PANEL_STATUSBAR].y = H - status_h;
    rects[PANEL_STATUSBAR].w = W;
    rects[PANEL_STATUSBAR].h = status_h;
}

int layout_hit_splitter(const Layout *l, int W, int H, int mx, int my) {
    int status_h = STATUSBAR_H;
    int usable_h = H - status_h;

    /* Left splitter */
    if (l->sidebar_visible) {
        if (mx >= l->sidebar_w && mx < l->sidebar_w + SPLITTER_THICK && my < usable_h)
            return 0;
    }

    /* Right splitter */
    if (l->chat_visible) {
        int rx = W - l->chat_w - SPLITTER_THICK;
        if (mx >= rx && mx < rx + SPLITTER_THICK && my < usable_h)
            return 1;
    }

    /* Bottom splitter */
    if (l->bottom_visible) {
        int bottom_h_actual = l->bottom_h + SPLITTER_THICK;
        int by = (usable_h - bottom_h_actual);
        if (my >= by && my < by + SPLITTER_THICK)
            return 2;
    }

    return -1;
}

void layout_begin_drag(Layout *l, int splitter, int mx, int my) {
    l->dragging     = true;
    l->drag_panel   = splitter;
    l->drag_start_x = mx;
    l->drag_start_y = my;
    if (splitter == 0) l->drag_start_val = l->sidebar_w;
    if (splitter == 1) l->drag_start_val = l->chat_w;
    if (splitter == 2) l->drag_start_val = l->bottom_h;
}

void layout_update_drag(Layout *l, int mx, int my) {
    if (!l->dragging) return;
    int delta_x = mx - l->drag_start_x;
    int delta_y = my - l->drag_start_y;
    if (l->drag_panel == 0) {
        l->sidebar_w = l->drag_start_val + delta_x;
        if (l->sidebar_w < 80)  l->sidebar_w = 80;
        if (l->sidebar_w > 600) l->sidebar_w = 600;
    } else if (l->drag_panel == 1) {
        l->chat_w = l->drag_start_val - delta_x;
        if (l->chat_w < 80)  l->chat_w = 80;
        if (l->chat_w > 600) l->chat_w = 600;
    } else if (l->drag_panel == 2) {
        l->bottom_h = l->drag_start_val - delta_y;
        if (l->bottom_h < 60)  l->bottom_h = 60;
        if (l->bottom_h > 600) l->bottom_h = 600;
    }
}

void layout_end_drag(Layout *l) {
    l->dragging = false;
}

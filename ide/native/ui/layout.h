#ifndef SOVEREIGN_LAYOUT_H
#define SOVEREIGN_LAYOUT_H

#include <windows.h>
#include <stdint.h>
#include <stdbool.h>

/* Fixed panel IDs */
typedef enum PanelId {
    PANEL_SIDEBAR    = 0,   /* left project tree */
    PANEL_EDITOR     = 1,   /* center editor area */
    PANEL_BOTTOM     = 2,   /* terminal / build output */
    PANEL_CHAT       = 3,   /* right AI chat */
    PANEL_STATUSBAR  = 4,   /* 1-row bottom strip */
    PANEL_COUNT      = 5
} PanelId;

#define SIDEBAR_DEFAULT_W   220
#define CHAT_DEFAULT_W      280
#define BOTTOM_DEFAULT_H    180
#define STATUSBAR_H          22
#define SPLITTER_THICK        4
#define MENU_H               20   /* approximation, real height from GetSystemMetrics */

typedef struct Layout {
    int sidebar_w;
    int chat_w;
    int bottom_h;
    bool sidebar_visible;
    bool chat_visible;
    bool bottom_visible;
    /* dragging state */
    bool dragging;
    int  drag_panel;   /* which splitter: 0=left, 1=right, 2=bottom */
    int  drag_start_x;
    int  drag_start_y;
    int  drag_start_val;
} Layout;

typedef struct PanelRect {
    int x, y, w, h;
} PanelRect;

void layout_init(Layout *l);
void layout_compute(const Layout *l, int total_w, int total_h, PanelRect rects[PANEL_COUNT]);

/* Splitter hit test — returns splitter index (0/1/2) or -1 */
int  layout_hit_splitter(const Layout *l, int total_w, int total_h, int mx, int my);

void layout_begin_drag(Layout *l, int splitter, int mx, int my);
void layout_update_drag(Layout *l, int mx, int my);
void layout_end_drag(Layout *l);

#endif

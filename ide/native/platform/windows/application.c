/*
 * Sovereign IDE — Win32 Application Entry
 * Owns the message loop, DPI awareness, and top-level window creation.
 */

#include "application.h"
#include "window.h"
#include "../../core/events.h"
#include "../../core/arena.h"
#include "../../core/strings.h"

#include <shellscalingapi.h>

static struct {
    HINSTANCE hinstance;
    bool      running;
    Arena     frame_arena;
} g_app;

static void app_set_dpi_awareness(void) {
    SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE);
}

void app_init(HINSTANCE hinstance) {
    g_app.hinstance = hinstance;
    g_app.running = true;

    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    app_set_dpi_awareness();
    arena_init_default(&g_app.frame_arena);
    strings_init();
    events_init();
}

int app_run(void) {
    MSG msg = {0};
    while (g_app.running) {
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_app.running = false;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        arena_reset(&g_app.frame_arena);
    }

    return (int)msg.wParam;
}

void app_request_quit(void) {
    PostQuitMessage(0);
    g_app.running = false;
}

void app_shutdown(void) {
    strings_shutdown();
    arena_destroy(&g_app.frame_arena);
    CoUninitialize();
}

HINSTANCE app_get_hinstance(void) {
    return g_app.hinstance;
}

Arena *app_frame_arena(void) {
    return &g_app.frame_arena;
}

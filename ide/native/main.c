/*
 * Sovereign IDE — Entry Point
 * Win32 wWinMain: init → window → message loop → shutdown.
 */

#include "platform/windows/application.h"
#include "platform/windows/shell.h"
#include "core/errors.h"

#define INITIAL_WIDTH  1280
#define INITIAL_HEIGHT  800

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrev, LPWSTR cmdLine, int nCmdShow) {
    (void)hPrev; (void)cmdLine; (void)nCmdShow;

    app_init(hInstance);

    SovResult r = shell_create(hInstance, INITIAL_WIDTH, INITIAL_HEIGHT);
    SOV_ASSERT(r == SOV_OK, "Failed to create shell window");

    int exit_code = app_run();

    app_shutdown();
    return exit_code;
}

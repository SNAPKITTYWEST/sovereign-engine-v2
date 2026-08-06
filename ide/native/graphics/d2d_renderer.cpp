/*
 * Sovereign IDE — Direct2D Renderer (C++ for COM vtable calls)
 */

#include <windows.h>
#include <d2d1_1.h>
#include <dwrite.h>
#include <stdint.h>

extern "C" {
#include "d2d_renderer.h"
}

static struct {
    ID2D1Factory           *factory;
    ID2D1HwndRenderTarget  *target;
    IDWriteFactory         *dwrite_factory;
    bool                    initialized;
} g_renderer;

extern "C" SovResult renderer_init(HWND hwnd) {
    HRESULT hr = D2D1CreateFactory(
        D2D1_FACTORY_TYPE_SINGLE_THREADED,
        &g_renderer.factory
    );
    if (FAILED(hr)) return SOV_ERR_ALLOC;

    RECT rc;
    GetClientRect(hwnd, &rc);

    D2D1_SIZE_U size = D2D1::SizeU(
        (UINT32)(rc.right - rc.left),
        (UINT32)(rc.bottom - rc.top)
    );

    D2D1_RENDER_TARGET_PROPERTIES rtprops = D2D1::RenderTargetProperties();
    D2D1_HWND_RENDER_TARGET_PROPERTIES hwndprops =
        D2D1::HwndRenderTargetProperties(hwnd, size);

    hr = g_renderer.factory->CreateHwndRenderTarget(
        rtprops, hwndprops, &g_renderer.target
    );
    if (FAILED(hr)) return SOV_ERR_ALLOC;

    hr = DWriteCreateFactory(
        DWRITE_FACTORY_TYPE_SHARED,
        __uuidof(IDWriteFactory),
        reinterpret_cast<IUnknown **>(&g_renderer.dwrite_factory)
    );
    if (FAILED(hr)) return SOV_ERR_ALLOC;

    g_renderer.initialized = true;
    return SOV_OK;
}

extern "C" void renderer_begin_frame(void) {
    if (!g_renderer.initialized) return;
    g_renderer.target->BeginDraw();
    D2D1_COLOR_F bg = { 0.12f, 0.12f, 0.14f, 1.0f };
    g_renderer.target->Clear(&bg);
}

extern "C" void renderer_end_frame(void) {
    if (!g_renderer.initialized) return;
    HRESULT hr = g_renderer.target->EndDraw();
    if (hr == (HRESULT)D2DERR_RECREATE_TARGET) {
        g_renderer.initialized = false;
    }
}

extern "C" void renderer_resize(uint32_t width, uint32_t height) {
    if (!g_renderer.initialized) return;
    D2D1_SIZE_U s = D2D1::SizeU(width, height);
    g_renderer.target->Resize(s);
}

extern "C" void renderer_shutdown(void) {
    if (g_renderer.target) { g_renderer.target->Release(); g_renderer.target = NULL; }
    if (g_renderer.factory) { g_renderer.factory->Release(); g_renderer.factory = NULL; }
    if (g_renderer.dwrite_factory) { g_renderer.dwrite_factory->Release(); g_renderer.dwrite_factory = NULL; }
    g_renderer.initialized = false;
}

extern "C" void *renderer_get_target(void) {
    return g_renderer.target;
}

extern "C" void *renderer_get_dwrite(void) {
    return g_renderer.dwrite_factory;
}

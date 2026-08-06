#ifndef SOVEREIGN_D2D_RENDERER_H
#define SOVEREIGN_D2D_RENDERER_H

#include <windows.h>
#include <stdint.h>
#include "../core/errors.h"

SovResult renderer_init(HWND hwnd);
void      renderer_begin_frame(void);
void      renderer_end_frame(void);
void      renderer_resize(uint32_t width, uint32_t height);
void      renderer_shutdown(void);

void *renderer_get_target(void);
void *renderer_get_dwrite(void);

#endif /* SOVEREIGN_D2D_RENDERER_H */

#ifndef SOVEREIGN_APPLICATION_H
#define SOVEREIGN_APPLICATION_H

#include <windows.h>
#include <stdbool.h>
#include "../../core/arena.h"

void       app_init(HINSTANCE hinstance);
int        app_run(void);
void       app_request_quit(void);
void       app_shutdown(void);
HINSTANCE  app_get_hinstance(void);
Arena     *app_frame_arena(void);

#endif /* SOVEREIGN_APPLICATION_H */

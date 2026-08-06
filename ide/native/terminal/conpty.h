#ifndef SOVEREIGN_CONPTY_H
#define SOVEREIGN_CONPTY_H

#include <windows.h>
#include <stdint.h>
#include <stdbool.h>
#include "../core/errors.h"

typedef struct Terminal Terminal;

SovResult terminal_create(Terminal **out, uint16_t cols, uint16_t rows);
SovResult terminal_write(Terminal *t, const char *data, size_t len);
SovResult terminal_read(Terminal *t, char *buf, size_t max_len, size_t *out_len);
void      terminal_resize(Terminal *t, uint16_t cols, uint16_t rows);
void      terminal_destroy(Terminal *t);
bool      terminal_is_alive(const Terminal *t);

#endif /* SOVEREIGN_CONPTY_H */

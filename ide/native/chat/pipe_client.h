#ifndef SOVEREIGN_PIPE_CLIENT_H
#define SOVEREIGN_PIPE_CLIENT_H

#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "../core/errors.h"

SovResult pipe_client_init(void);
SovResult pipe_client_connect(void);
SovResult pipe_client_send(const uint8_t *data, size_t len);
SovResult pipe_client_recv(uint8_t *out, size_t max_len, size_t *out_len);
bool      pipe_client_is_connected(void);
void      pipe_client_disconnect(void);
void      pipe_client_shutdown(void);

#endif /* SOVEREIGN_PIPE_CLIENT_H */

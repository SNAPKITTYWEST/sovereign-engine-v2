/*
 * Sovereign IDE — Named Pipe Client
 * Connects to the Elixir SovereignChat process via \\.\pipe\sovereign-ide-chat.
 * Framed binary protocol per contract section 8.
 */

#include "pipe_client.h"
#include "protocol.h"
#include "../core/errors.h"
#include "../core/arena.h"

#include <string.h>

#define PIPE_NAME L"\\\\.\\pipe\\sovereign-ide-chat"
#define PIPE_BUFFER_SIZE (64 * 1024)
#define RECONNECT_DELAY_MS 1000
#define MAX_RECONNECT_ATTEMPTS 10

static struct {
    HANDLE pipe;
    bool   connected;
    Arena  recv_arena;
    uint8_t recv_buf[PIPE_BUFFER_SIZE];
} g_pipe;

SovResult pipe_client_init(void) {
    g_pipe.pipe = INVALID_HANDLE_VALUE;
    g_pipe.connected = false;
    arena_init(&g_pipe.recv_arena, 256 * 1024);
    return SOV_OK;
}

SovResult pipe_client_connect(void) {
    for (int attempt = 0; attempt < MAX_RECONNECT_ATTEMPTS; attempt++) {
        g_pipe.pipe = CreateFileW(
            PIPE_NAME,
            GENERIC_READ | GENERIC_WRITE,
            0, NULL,
            OPEN_EXISTING,
            FILE_FLAG_OVERLAPPED,
            NULL
        );

        if (g_pipe.pipe != INVALID_HANDLE_VALUE) {
            DWORD mode = PIPE_READMODE_MESSAGE;
            SetNamedPipeHandleState(g_pipe.pipe, &mode, NULL, NULL);
            g_pipe.connected = true;
            return SOV_OK;
        }

        if (GetLastError() != ERROR_PIPE_BUSY) {
            Sleep(RECONNECT_DELAY_MS);
        } else {
            WaitNamedPipeW(PIPE_NAME, RECONNECT_DELAY_MS);
        }
    }

    return SOV_ERR_PIPE;
}

SovResult pipe_client_send(const uint8_t *data, size_t len) {
    if (!g_pipe.connected) return SOV_ERR_PIPE;

    DWORD written;
    BOOL ok = WriteFile(g_pipe.pipe, data, (DWORD)len, &written, NULL);
    if (!ok || written != (DWORD)len) return SOV_ERR_PIPE;

    return SOV_OK;
}

SovResult pipe_client_recv(uint8_t *out, size_t max_len, size_t *out_len) {
    if (!g_pipe.connected) return SOV_ERR_PIPE;

    DWORD read;
    BOOL ok = ReadFile(g_pipe.pipe, out, (DWORD)max_len, &read, NULL);
    if (!ok) {
        DWORD err = GetLastError();
        if (err == ERROR_MORE_DATA) {
            *out_len = read;
            return SOV_OK;
        }
        g_pipe.connected = false;
        return SOV_ERR_PIPE;
    }

    *out_len = read;
    return SOV_OK;
}

bool pipe_client_is_connected(void) {
    return g_pipe.connected;
}

void pipe_client_disconnect(void) {
    if (g_pipe.pipe != INVALID_HANDLE_VALUE) {
        CloseHandle(g_pipe.pipe);
        g_pipe.pipe = INVALID_HANDLE_VALUE;
    }
    g_pipe.connected = false;
}

void pipe_client_shutdown(void) {
    pipe_client_disconnect();
    arena_destroy(&g_pipe.recv_arena);
}

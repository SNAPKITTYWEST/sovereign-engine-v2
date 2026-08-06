/*
 * Sovereign IDE — ConPTY Terminal
 * Windows Pseudo Console for embedded terminal.
 * ConPTY APIs are loaded dynamically since MinGW headers may lack them.
 */

#include "conpty.h"
#include "../core/arena.h"
#include <stdlib.h>
#include <string.h>

/* ConPTY types and dynamic loading (Win10 1809+) */
typedef void *HPCON;

typedef HRESULT (WINAPI *PFN_CreatePseudoConsole)(COORD, HANDLE, HANDLE, DWORD, HPCON *);
typedef HRESULT (WINAPI *PFN_ResizePseudoConsole)(HPCON, COORD);
typedef void    (WINAPI *PFN_ClosePseudoConsole)(HPCON);

#ifndef PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE
#define PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE 0x00020016
#endif

static PFN_CreatePseudoConsole pfnCreatePseudoConsole;
static PFN_ResizePseudoConsole pfnResizePseudoConsole;
static PFN_ClosePseudoConsole  pfnClosePseudoConsole;
static bool conpty_loaded = false;

static bool conpty_load(void) {
    if (conpty_loaded) return pfnCreatePseudoConsole != NULL;
    conpty_loaded = true;
    HMODULE k32 = GetModuleHandleW(L"kernel32.dll");
    if (!k32) return false;
    pfnCreatePseudoConsole = (PFN_CreatePseudoConsole)(void *)GetProcAddress(k32, "CreatePseudoConsole");
    pfnResizePseudoConsole = (PFN_ResizePseudoConsole)(void *)GetProcAddress(k32, "ResizePseudoConsole");
    pfnClosePseudoConsole  = (PFN_ClosePseudoConsole)(void *)GetProcAddress(k32, "ClosePseudoConsole");
    return pfnCreatePseudoConsole != NULL;
}

struct Terminal {
    HPCON               hpc;
    HANDLE              pipe_in;
    HANDLE              pipe_out;
    HANDLE              pipe_pty_in;
    HANDLE              pipe_pty_out;
    PROCESS_INFORMATION pi;
    bool                alive;
};

SovResult terminal_create(Terminal **out, uint16_t cols, uint16_t rows) {
    if (!conpty_load()) return SOV_ERR_ALLOC;

    Terminal *t = (Terminal *)calloc(1, sizeof(Terminal));
    if (!t) return SOV_ERR_ALLOC;

    HANDLE pipe_pty_in, pipe_in;
    HANDLE pipe_pty_out, pipe_out;
    CreatePipe(&pipe_pty_in, &pipe_in, NULL, 0);
    CreatePipe(&pipe_out, &pipe_pty_out, NULL, 0);

    COORD size = { .X = (SHORT)cols, .Y = (SHORT)rows };
    HRESULT hr = pfnCreatePseudoConsole(size, pipe_pty_in, pipe_pty_out, 0, &t->hpc);
    if (FAILED(hr)) {
        CloseHandle(pipe_pty_in);
        CloseHandle(pipe_in);
        CloseHandle(pipe_pty_out);
        CloseHandle(pipe_out);
        free(t);
        return SOV_ERR_ALLOC;
    }

    t->pipe_in = pipe_in;
    t->pipe_out = pipe_out;
    t->pipe_pty_in = pipe_pty_in;
    t->pipe_pty_out = pipe_pty_out;

    STARTUPINFOEXW si;
    memset(&si, 0, sizeof(si));
    si.StartupInfo.cb = sizeof(si);

    SIZE_T attr_size = 0;
    InitializeProcThreadAttributeList(NULL, 1, 0, &attr_size);
    si.lpAttributeList = (PPROC_THREAD_ATTRIBUTE_LIST)malloc(attr_size);
    InitializeProcThreadAttributeList(si.lpAttributeList, 1, 0, &attr_size);
    UpdateProcThreadAttribute(si.lpAttributeList, 0,
        PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, t->hpc, sizeof(HPCON), NULL, NULL);

    wchar_t cmd[] = L"cmd.exe";
    CreateProcessW(NULL, cmd, NULL, NULL, FALSE,
        EXTENDED_STARTUPINFO_PRESENT, NULL, NULL,
        &si.StartupInfo, &t->pi);

    DeleteProcThreadAttributeList(si.lpAttributeList);
    free(si.lpAttributeList);

    CloseHandle(pipe_pty_in);
    CloseHandle(pipe_pty_out);

    t->alive = true;
    *out = t;
    return SOV_OK;
}

SovResult terminal_write(Terminal *t, const char *data, size_t len) {
    DWORD written;
    if (!WriteFile(t->pipe_in, data, (DWORD)len, &written, NULL))
        return SOV_ERR_IO;
    return SOV_OK;
}

SovResult terminal_read(Terminal *t, char *buf, size_t max_len, size_t *out_len) {
    DWORD available = 0;
    if (!PeekNamedPipe(t->pipe_out, NULL, 0, NULL, &available, NULL) || available == 0) {
        *out_len = 0;
        return SOV_OK;
    }

    DWORD to_read = (available < (DWORD)max_len) ? available : (DWORD)max_len;
    DWORD nread = 0;
    if (!ReadFile(t->pipe_out, buf, to_read, &nread, NULL))
        return SOV_ERR_IO;

    *out_len = nread;
    return SOV_OK;
}

void terminal_resize(Terminal *t, uint16_t cols, uint16_t rows) {
    if (pfnResizePseudoConsole) {
        COORD size = { .X = (SHORT)cols, .Y = (SHORT)rows };
        pfnResizePseudoConsole(t->hpc, size);
    }
}

bool terminal_is_alive(const Terminal *t) {
    if (!t->alive) return false;
    DWORD exit_code;
    GetExitCodeProcess(t->pi.hProcess, &exit_code);
    return exit_code == STILL_ACTIVE;
}

void terminal_destroy(Terminal *t) {
    if (!t) return;
    if (pfnClosePseudoConsole) pfnClosePseudoConsole(t->hpc);
    CloseHandle(t->pipe_in);
    CloseHandle(t->pipe_out);
    TerminateProcess(t->pi.hProcess, 0);
    CloseHandle(t->pi.hProcess);
    CloseHandle(t->pi.hThread);
    free(t);
}

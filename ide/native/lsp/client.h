#ifndef SOVEREIGN_LSP_CLIENT_H
#define SOVEREIGN_LSP_CLIENT_H

#include <windows.h>
#include <stdbool.h>
#include <stdint.h>
#include "../core/errors.h"

typedef struct LspClient LspClient;

typedef struct LspDiagnostic {
    wchar_t  file[MAX_PATH];
    uint32_t line;        /* 0-based */
    uint32_t col;         /* 0-based */
    uint32_t severity;    /* 1=error 2=warning 3=info 4=hint */
    char     message[512];
} LspDiagnostic;

#define LSP_MAX_DIAG 256

typedef struct LspDiagList {
    LspDiagnostic entries[LSP_MAX_DIAG];
    int           count;
    wchar_t       uri[MAX_PATH];   /* file these diags belong to */
} LspDiagList;

/* Called on UI thread after each publishDiagnostics notification */
typedef void (*lsp_diag_cb)(const LspDiagList *diags, void *ctx);

SovResult lsp_client_start(LspClient **out, const wchar_t *server_cmd,
                            lsp_diag_cb on_diag, void *cb_ctx);
SovResult lsp_client_initialize(LspClient *c, const wchar_t *root_path);
SovResult lsp_client_open(LspClient *c, const wchar_t *path,
                           const char *text, size_t len);
SovResult lsp_client_change(LspClient *c, const wchar_t *path,
                             const char *text, size_t len, int version);
void      lsp_client_tick(LspClient *c);   /* pump: call from message loop */
void      lsp_client_shutdown(LspClient *c);

#endif

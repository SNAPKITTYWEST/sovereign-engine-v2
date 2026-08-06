/*
 * Sovereign IDE — LSP Client
 * JSON-RPC 2.0 over stdio pipes to clangd (or any LSP server).
 * Handles: initialize, initialized, textDocument/didOpen, didChange,
 * shutdown, and inbound publishDiagnostics notifications.
 *
 * JSON is hand-built (no external lib). Parsing is minimal: we walk
 * the response bytes looking for the fields we need.
 */

#include "client.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── JSON helpers ────────────────────────────────────────────── */

/* Escape a UTF-8 string into a JSON string (caller provides buf). */
static int json_escape(const char *src, char *dst, int cap) {
    int n = 0;
    for (; *src && n < cap - 2; src++) {
        unsigned char c = (unsigned char)*src;
        if      (c == '"')  { dst[n++]='\\'; dst[n++]='"'; }
        else if (c == '\\') { dst[n++]='\\'; dst[n++]='\\'; }
        else if (c == '\n') { dst[n++]='\\'; dst[n++]='n'; }
        else if (c == '\r') { dst[n++]='\\'; dst[n++]='r'; }
        else if (c == '\t') { dst[n++]='\\'; dst[n++]='t'; }
        else                { dst[n++]=(char)c; }
    }
    dst[n] = '\0';
    return n;
}

/* Wide path → file:/// URI in UTF-8 */
static void path_to_uri(const wchar_t *path, char *uri, int cap) {
    char narrow[MAX_PATH * 2];
    WideCharToMultiByte(CP_UTF8, 0, path, -1, narrow, sizeof(narrow), NULL, NULL);
    /* Replace backslashes */
    for (char *p = narrow; *p; p++) if (*p == '\\') *p = '/';
    snprintf(uri, (size_t)cap, "file:///%s", narrow);
}

/* ── Minimal JSON parser helpers ─────────────────────────────── */

static const char *json_find_key(const char *json, const char *key) {
    char needle[128];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    return strstr(json, needle);
}

static int json_int_after_key(const char *json, const char *key, int def) {
    const char *p = json_find_key(json, key);
    if (!p) return def;
    p += strlen(key) + 2;
    while (*p == ' ' || *p == ':' || *p == '"') p++;
    if (*p == '\0') return def;
    return atoi(p);
}

static bool json_str_after_key(const char *json, const char *key,
                                char *out, int cap) {
    const char *p = json_find_key(json, key);
    if (!p) return false;
    p += strlen(key) + 2;
    while (*p == ' ' || *p == ':') p++;
    if (*p != '"') return false;
    p++;
    int n = 0;
    while (*p && *p != '"' && n < cap - 1) {
        if (*p == '\\' && *(p+1)) { p++; }
        out[n++] = *p++;
    }
    out[n] = '\0';
    return true;
}

/* ── RPC framing ─────────────────────────────────────────────── */

struct LspClient {
    HANDLE  pipe_stdin;   /* write to child stdin  */
    HANDLE  pipe_stdout;  /* read from child stdout */
    PROCESS_INFORMATION pi;
    bool    alive;

    int          next_id;
    lsp_diag_cb  on_diag;
    void        *cb_ctx;

    /* Read buffer for partial Content-Length frames */
    char   rbuf[1 << 20];   /* 1 MB */
    int    rbuf_len;
};

static SovResult lsp_send(LspClient *c, const char *body, int body_len) {
    char header[64];
    int hlen = snprintf(header, sizeof(header),
                        "Content-Length: %d\r\n\r\n", body_len);
    DWORD written;
    if (!WriteFile(c->pipe_stdin, header, (DWORD)hlen, &written, NULL))
        return SOV_ERR_IO;
    if (!WriteFile(c->pipe_stdin, body, (DWORD)body_len, &written, NULL))
        return SOV_ERR_IO;
    return SOV_OK;
}

/* Build a JSON-RPC request and send it */
static SovResult lsp_request(LspClient *c, const char *method,
                              const char *params_json) {
    char body[1 << 18];
    int n = snprintf(body, sizeof(body),
        "{\"jsonrpc\":\"2.0\",\"id\":%d,\"method\":\"%s\",\"params\":%s}",
        c->next_id++, method, params_json ? params_json : "null");
    return lsp_send(c, body, n);
}

/* Build a JSON-RPC notification (no id) and send it */
static SovResult lsp_notify(LspClient *c, const char *method,
                             const char *params_json) {
    char body[1 << 18];
    int n = snprintf(body, sizeof(body),
        "{\"jsonrpc\":\"2.0\",\"method\":\"%s\",\"params\":%s}",
        method, params_json ? params_json : "{}");
    return lsp_send(c, body, n);
}

/* ── Diagnostics parser ──────────────────────────────────────── */

static void parse_diagnostics(LspClient *c, const char *json) {
    LspDiagList list;
    memset(&list, 0, sizeof(list));

    /* Extract URI */
    char uri[MAX_PATH * 2] = {0};
    json_str_after_key(json, "uri", uri, sizeof(uri));
    /* Strip file:/// prefix */
    const char *path = uri;
    if (strncmp(path, "file:///", 8) == 0) path += 8;
    MultiByteToWideChar(CP_UTF8, 0, path, -1, list.uri, MAX_PATH);
    /* Restore backslashes on Windows */
    for (wchar_t *p = list.uri; *p; p++) if (*p == L'/') *p = L'\\';

    /* Walk diagnostics array */
    const char *p = strstr(json, "\"diagnostics\"");
    if (!p) goto done;
    p = strchr(p, '[');
    if (!p) goto done;
    p++;

    while (*p && list.count < LSP_MAX_DIAG) {
        /* Find next object */
        const char *obj = strchr(p, '{');
        if (!obj) break;
        /* Find matching } — naive single-level scan */
        const char *end = obj + 1;
        int depth = 1;
        while (*end && depth > 0) {
            if (*end == '{') depth++;
            else if (*end == '}') depth--;
            end++;
        }
        if (depth != 0) break;

        /* Extract a diagnostic object [obj, end) */
        char obj_buf[2048];
        int obj_len = (int)(end - obj);
        if (obj_len > (int)sizeof(obj_buf) - 1) obj_len = (int)sizeof(obj_buf) - 1;
        memcpy(obj_buf, obj, (size_t)obj_len);
        obj_buf[obj_len] = '\0';

        LspDiagnostic *d = &list.entries[list.count];

        /* line/character from "start" */
        const char *rng = strstr(obj_buf, "\"range\"");
        if (rng) {
            const char *start = strstr(rng, "\"start\"");
            if (start) {
                d->line = (uint32_t)json_int_after_key(start, "line", 0);
                d->col  = (uint32_t)json_int_after_key(start, "character", 0);
            }
        }
        d->severity = (uint32_t)json_int_after_key(obj_buf, "severity", 1);
        json_str_after_key(obj_buf, "message", d->message, 512);
        wcscpy_s(d->file, MAX_PATH, list.uri);

        list.count++;
        p = end;
    }

done:
    if (c->on_diag) c->on_diag(&list, c->cb_ctx);
}

/* ── Dispatch one complete JSON message ──────────────────────── */

static void dispatch_message(LspClient *c, const char *json) {
    /* Only care about notifications right now */
    const char *method_pos = strstr(json, "\"method\"");
    if (!method_pos) return;

    char method[128] = {0};
    json_str_after_key(json, "method", method, sizeof(method));

    if (strcmp(method, "textDocument/publishDiagnostics") == 0) {
        parse_diagnostics(c, json);
    }
    /* Other notifications (window/logMessage, $/progress, etc.) ignored */
}

/* ── Public API ──────────────────────────────────────────────── */

SovResult lsp_client_start(LspClient **out, const wchar_t *server_cmd,
                            lsp_diag_cb on_diag, void *cb_ctx) {
    LspClient *c = (LspClient *)calloc(1, sizeof(LspClient));
    if (!c) return SOV_ERR_ALLOC;
    c->on_diag  = on_diag;
    c->cb_ctx   = cb_ctx;
    c->next_id  = 1;
    c->alive    = false;

    SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };

    HANDLE child_stdin_rd, child_stdin_wr;
    HANDLE child_stdout_rd, child_stdout_wr;

    if (!CreatePipe(&child_stdin_rd,  &child_stdin_wr,  &sa, 0)) goto fail;
    if (!CreatePipe(&child_stdout_rd, &child_stdout_wr, &sa, 0)) {
        CloseHandle(child_stdin_rd); CloseHandle(child_stdin_wr); goto fail;
    }
    SetHandleInformation(child_stdin_wr,  HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(child_stdout_rd, HANDLE_FLAG_INHERIT, 0);

    c->pipe_stdin  = child_stdin_wr;
    c->pipe_stdout = child_stdout_rd;

    STARTUPINFOW si = {0};
    si.cb         = sizeof(si);
    si.dwFlags    = STARTF_USESTDHANDLES;
    si.hStdInput  = child_stdin_rd;
    si.hStdOutput = child_stdout_wr;
    si.hStdError  = GetStdHandle(STD_ERROR_HANDLE);

    wchar_t cmd[MAX_PATH + 64];
    wcscpy_s(cmd, MAX_PATH + 64, server_cmd);

    BOOL ok = CreateProcessW(NULL, cmd, NULL, NULL, TRUE,
                             CREATE_NO_WINDOW, NULL, NULL, &si, &c->pi);

    CloseHandle(child_stdin_rd);
    CloseHandle(child_stdout_wr);

    if (!ok) goto fail;

    c->alive = true;
    *out = c;
    return SOV_OK;

fail:
    free(c);
    return SOV_ERR_IO;
}

SovResult lsp_client_initialize(LspClient *c, const wchar_t *root_path) {
    if (!c->alive) return SOV_ERR_IO;

    char root_uri[MAX_PATH * 3];
    path_to_uri(root_path, root_uri, sizeof(root_uri));

    char params[MAX_PATH * 3 + 256];
    snprintf(params, sizeof(params),
        "{\"processId\":%lu,"
        "\"rootUri\":\"%s\","
        "\"capabilities\":{"
            "\"textDocument\":{"
                "\"publishDiagnostics\":{\"relatedInformation\":false}"
            "}"
        "}}",
        (unsigned long)GetCurrentProcessId(), root_uri);

    SovResult r = lsp_request(c, "initialize", params);
    if (r != SOV_OK) return r;

    /* Send initialized after a tick (clangd expects response first,
     * but we're async — send immediately, clangd handles it fine) */
    return lsp_notify(c, "initialized", "{}");
}

SovResult lsp_client_open(LspClient *c, const wchar_t *path,
                           const char *text, size_t len) {
    if (!c->alive) return SOV_ERR_IO;

    char uri[MAX_PATH * 3];
    path_to_uri(path, uri, sizeof(uri));

    /* Detect language from extension */
    const char *lang = "c";
    const wchar_t *ext = wcsrchr(path, L'.');
    if (ext) {
        if (_wcsicmp(ext, L".cpp") == 0 || _wcsicmp(ext, L".hpp") == 0 ||
            _wcsicmp(ext, L".cc")  == 0 || _wcsicmp(ext, L".cxx") == 0)
            lang = "cpp";
    }

    /* Escape text into JSON string */
    char *esc = (char *)malloc(len * 2 + 8);
    if (!esc) return SOV_ERR_ALLOC;
    json_escape(text, esc, (int)(len * 2 + 8));

    char *params = (char *)malloc(len * 2 + 512);
    if (!params) { free(esc); return SOV_ERR_ALLOC; }
    snprintf(params, len * 2 + 512,
        "{\"textDocument\":{"
            "\"uri\":\"%s\","
            "\"languageId\":\"%s\","
            "\"version\":1,"
            "\"text\":\"%s\""
        "}}",
        uri, lang, esc);

    SovResult r = lsp_notify(c, "textDocument/didOpen", params);
    free(esc);
    free(params);
    return r;
}

SovResult lsp_client_change(LspClient *c, const wchar_t *path,
                             const char *text, size_t len, int version) {
    if (!c->alive) return SOV_ERR_IO;

    char uri[MAX_PATH * 3];
    path_to_uri(path, uri, sizeof(uri));

    char *esc = (char *)malloc(len * 2 + 8);
    if (!esc) return SOV_ERR_ALLOC;
    json_escape(text, esc, (int)(len * 2 + 8));

    char *params = (char *)malloc(len * 2 + 512);
    if (!params) { free(esc); return SOV_ERR_ALLOC; }
    snprintf(params, len * 2 + 512,
        "{\"textDocument\":{"
            "\"uri\":\"%s\","
            "\"version\":%d"
        "},"
        "\"contentChanges\":[{\"text\":\"%s\"}]}",
        uri, version, esc);

    SovResult r = lsp_notify(c, "textDocument/didChange", params);
    free(esc);
    free(params);
    return r;
}

void lsp_client_tick(LspClient *c) {
    if (!c->alive) return;

    /* Non-blocking drain of stdout pipe */
    DWORD avail = 0;
    while (PeekNamedPipe(c->pipe_stdout, NULL, 0, NULL, &avail, NULL) && avail > 0) {
        int space = (int)sizeof(c->rbuf) - c->rbuf_len - 1;
        if (space <= 0) { c->rbuf_len = 0; break; }  /* overflow: reset */
        DWORD to_read = (avail < (DWORD)space) ? avail : (DWORD)space;
        DWORD nread = 0;
        if (!ReadFile(c->pipe_stdout, c->rbuf + c->rbuf_len, to_read, &nread, NULL))
            break;
        c->rbuf_len += (int)nread;
        c->rbuf[c->rbuf_len] = '\0';
    }

    /* Parse complete Content-Length frames */
    char *p = c->rbuf;
    int remaining = c->rbuf_len;

    while (remaining > 0) {
        /* Look for "Content-Length: N\r\n\r\n" */
        /* strnstr not in MinGW — manual search with length guard */
        char *hdr = NULL;
        for (int si = 0; si <= remaining - 16; si++) {
            if (memcmp(p + si, "Content-Length: ", 16) == 0) {
                hdr = p + si; break;
            }
        }
        if (!hdr) break;

        int content_len = atoi(hdr + 16);
        if (content_len <= 0) { remaining = 0; break; }

        /* Find end of header (\r\n\r\n) */
        char *body = strstr(hdr, "\r\n\r\n");
        if (!body) break;
        body += 4;

        int consumed = (int)(body - p);
        int body_avail = remaining - consumed;
        if (body_avail < content_len) break;  /* incomplete body, wait */

        /* Process this message */
        body[content_len] = '\0';
        dispatch_message(c, body);

        p         = body + content_len;
        remaining = remaining - consumed - content_len;
    }

    /* Compact buffer */
    if (remaining > 0 && p != c->rbuf)
        memmove(c->rbuf, p, (size_t)remaining);
    c->rbuf_len = remaining;
}

void lsp_client_shutdown(LspClient *c) {
    if (!c) return;
    if (c->alive) {
        lsp_request(c, "shutdown", NULL);
        lsp_notify(c, "exit", NULL);
        WaitForSingleObject(c->pi.hProcess, 2000);
        TerminateProcess(c->pi.hProcess, 0);
        CloseHandle(c->pi.hProcess);
        CloseHandle(c->pi.hThread);
    }
    CloseHandle(c->pipe_stdin);
    CloseHandle(c->pipe_stdout);
    free(c);
}

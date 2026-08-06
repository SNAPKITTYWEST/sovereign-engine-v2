/*
 * Sovereign IDE — Document
 * File open/save with UTF-8 + CRLF normalization.
 */

#include "document.h"
#include <windows.h>
#include <stdlib.h>
#include <string.h>

void document_new(Document *doc) {
    doc->buffer = buffer_create("", 0);
    doc->path[0] = L'\0';
    doc->has_path = false;
    doc->line_ending = LE_LF;
}

static LineEnding detect_line_ending(const char *text, size_t len) {
    for (size_t i = 0; i + 1 < len; i++) {
        if (text[i] == '\r' && text[i+1] == '\n') return LE_CRLF;
    }
    for (size_t i = 0; i < len; i++) {
        if (text[i] == '\r') return LE_CR;
    }
    return LE_LF;
}

/* Normalize CRLF/CR to LF for internal storage */
static char *normalize_to_lf(const char *src, size_t src_len, size_t *out_len) {
    char *dst = (char *)malloc(src_len + 1);
    size_t j = 0;
    for (size_t i = 0; i < src_len; i++) {
        if (src[i] == '\r') {
            dst[j++] = '\n';
            if (i + 1 < src_len && src[i+1] == '\n') i++;
        } else {
            dst[j++] = src[i];
        }
    }
    dst[j] = '\0';
    *out_len = j;
    return dst;
}

SovResult document_open(Document *doc, const wchar_t *path) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return SOV_ERR_IO;

    LARGE_INTEGER file_size;
    GetFileSizeEx(h, &file_size);
    if (file_size.QuadPart > 256 * 1024 * 1024) {
        CloseHandle(h);
        return SOV_ERR_IO;
    }

    size_t sz = (size_t)file_size.QuadPart;
    char *raw = (char *)malloc(sz + 1);
    DWORD nread = 0;
    ReadFile(h, raw, (DWORD)sz, &nread, NULL);
    CloseHandle(h);
    raw[nread] = '\0';

    /* Skip UTF-8 BOM if present */
    const char *text = raw;
    size_t text_len = nread;
    if (text_len >= 3 &&
        (unsigned char)text[0] == 0xEF &&
        (unsigned char)text[1] == 0xBB &&
        (unsigned char)text[2] == 0xBF) {
        text += 3;
        text_len -= 3;
    }

    doc->line_ending = detect_line_ending(text, text_len);

    size_t norm_len;
    char *norm = normalize_to_lf(text, text_len, &norm_len);
    free(raw);

    doc->buffer = buffer_create(norm, norm_len);
    free(norm);

    wcscpy_s(doc->path, MAX_PATH, path);
    doc->has_path = true;
    return SOV_OK;
}

SovResult document_save(Document *doc) {
    if (!doc->has_path) return SOV_ERR_IO;
    SovResult r = document_save_as(doc, doc->path);
    return r;
}

SovResult document_save_as(Document *doc, const wchar_t *path) {
    size_t len = buffer_length(doc->buffer);
    char *content = (char *)malloc(len + 1);
    buffer_read(doc->buffer, 0, content, len);
    content[len] = '\0';

    /* Re-apply original line endings */
    char *output = content;
    size_t out_len = len;
    char *crlf_buf = NULL;

    if (doc->line_ending == LE_CRLF) {
        /* count newlines to allocate */
        size_t nl = 0;
        for (size_t i = 0; i < len; i++) if (content[i] == '\n') nl++;
        crlf_buf = (char *)malloc(len + nl + 1);
        size_t j = 0;
        for (size_t i = 0; i < len; i++) {
            if (content[i] == '\n') crlf_buf[j++] = '\r';
            crlf_buf[j++] = content[i];
        }
        crlf_buf[j] = '\0';
        output = crlf_buf;
        out_len = j;
    }

    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, NULL,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        free(content);
        free(crlf_buf);
        return SOV_ERR_IO;
    }

    DWORD written;
    WriteFile(h, output, (DWORD)out_len, &written, NULL);
    CloseHandle(h);

    free(content);
    free(crlf_buf);

    wcscpy_s(doc->path, MAX_PATH, path);
    doc->has_path = true;
    buffer_mark_clean(doc->buffer);
    return SOV_OK;
}

bool document_is_dirty(const Document *doc) {
    return buffer_is_dirty(doc->buffer);
}

void document_destroy(Document *doc) {
    if (doc->buffer) {
        buffer_destroy(doc->buffer);
        doc->buffer = NULL;
    }
}

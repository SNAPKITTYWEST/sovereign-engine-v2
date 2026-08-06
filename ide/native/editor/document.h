#ifndef SOVEREIGN_DOCUMENT_H
#define SOVEREIGN_DOCUMENT_H

#include <windows.h>
#include "buffer.h"
#include "../core/errors.h"
#include <stdbool.h>
#include <stddef.h>

typedef enum LineEnding { LE_LF, LE_CRLF, LE_CR } LineEnding;

typedef struct Document {
    Buffer     *buffer;
    wchar_t     path[MAX_PATH];
    LineEnding  line_ending;
    bool        has_path;
} Document;

SovResult document_open(Document *doc, const wchar_t *path);
SovResult document_save(Document *doc);
SovResult document_save_as(Document *doc, const wchar_t *path);
void      document_new(Document *doc);
void      document_destroy(Document *doc);
bool      document_is_dirty(const Document *doc);

#endif

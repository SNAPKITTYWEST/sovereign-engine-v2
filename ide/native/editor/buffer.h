#ifndef SOVEREIGN_BUFFER_H
#define SOVEREIGN_BUFFER_H

#include <stddef.h>
#include <stdbool.h>

typedef struct Buffer Buffer;

Buffer *buffer_create(const char *text, size_t len);
void    buffer_destroy(Buffer *b);
size_t  buffer_length(const Buffer *b);
size_t  buffer_line_count(const Buffer *b);
void    buffer_insert(Buffer *b, size_t offset, const char *text, size_t len);
void    buffer_delete(Buffer *b, size_t offset, size_t len);
size_t  buffer_read(const Buffer *b, size_t offset, char *out, size_t max_len);

void    buffer_undo(Buffer *b);
void    buffer_redo(Buffer *b);
bool    buffer_can_undo(const Buffer *b);
bool    buffer_can_redo(const Buffer *b);
bool    buffer_is_dirty(const Buffer *b);
void    buffer_mark_clean(Buffer *b);

size_t  buffer_line_start(const Buffer *b, size_t line);
size_t  buffer_line_length(const Buffer *b, size_t line);

#endif /* SOVEREIGN_BUFFER_H */

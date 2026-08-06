/*
 * Sovereign IDE — Piece Table Buffer
 * Supports insert, delete, undo/redo, line indexing.
 */

#include "buffer.h"
#include "../core/arena.h"
#include <string.h>
#include <assert.h>
#include <stdlib.h>

#define ADD_BUFFER_INITIAL_CAP (256 * 1024)
#define UNDO_STACK_CAP 1024

typedef enum PieceSource { PIECE_ORIGINAL, PIECE_ADD } PieceSource;

typedef struct Piece {
    PieceSource    source;
    size_t         start;
    size_t         length;
    struct Piece  *prev;
    struct Piece  *next;
} Piece;

typedef enum UndoKind { UNDO_INSERT, UNDO_DELETE } UndoKind;

typedef struct UndoEntry {
    UndoKind kind;
    size_t   offset;
    size_t   len;
    char    *deleted_text;
} UndoEntry;

struct Buffer {
    Arena   arena;

    char   *original;
    size_t  original_len;

    char   *add_buf;
    size_t  add_len;
    size_t  add_cap;

    Piece   sentinel;
    size_t  total_len;
    size_t  line_count;

    UndoEntry undo_stack[UNDO_STACK_CAP];
    int       undo_top;
    int       redo_top;
    bool      dirty;
};

static const char *piece_data(const Buffer *b, const Piece *p) {
    return (p->source == PIECE_ORIGINAL)
        ? b->original + p->start
        : b->add_buf + p->start;
}

static size_t count_newlines(const char *text, size_t len) {
    size_t n = 0;
    for (size_t i = 0; i < len; i++) {
        if (text[i] == '\n') n++;
    }
    return n;
}

static void append_to_add(Buffer *b, const char *text, size_t len) {
    if (b->add_len + len > b->add_cap) {
        size_t new_cap = b->add_cap * 2;
        while (new_cap < b->add_len + len) new_cap *= 2;
        char *new_buf = (char *)arena_alloc(&b->arena, new_cap);
        memcpy(new_buf, b->add_buf, b->add_len);
        b->add_buf = new_buf;
        b->add_cap = new_cap;
    }
    memcpy(b->add_buf + b->add_len, text, len);
    b->add_len += len;
}

static Piece *alloc_piece(Buffer *b) {
    return (Piece *)arena_alloc(&b->arena, sizeof(Piece));
}

static void find_piece_at(Buffer *b, size_t offset, Piece **out_piece, size_t *out_local) {
    Piece *p = b->sentinel.next;
    size_t pos = 0;
    while (p != &b->sentinel && pos + p->length <= offset) {
        pos += p->length;
        p = p->next;
    }
    *out_piece = p;
    *out_local = offset - pos;
}

Buffer *buffer_create(const char *text, size_t len) {
    Arena a;
    arena_init(&a, 8 * 1024 * 1024);

    Buffer *b = (Buffer *)arena_alloc_zero(&a, sizeof(Buffer));
    b->arena = a;

    b->original = (char *)arena_alloc(&b->arena, len + 1);
    memcpy(b->original, text, len);
    b->original[len] = '\0';
    b->original_len = len;

    b->add_cap = ADD_BUFFER_INITIAL_CAP;
    b->add_buf = (char *)arena_alloc(&b->arena, b->add_cap);
    b->add_len = 0;

    if (len > 0) {
        Piece *first = alloc_piece(b);
        first->source = PIECE_ORIGINAL;
        first->start  = 0;
        first->length = len;
        b->sentinel.next = first;
        b->sentinel.prev = first;
        first->prev = &b->sentinel;
        first->next = &b->sentinel;
    } else {
        b->sentinel.next = &b->sentinel;
        b->sentinel.prev = &b->sentinel;
    }

    b->total_len = len;
    b->line_count = 1 + count_newlines(text, len);
    b->undo_top = 0;
    b->redo_top = 0;
    b->dirty = false;

    return b;
}

void buffer_destroy(Buffer *b) {
    for (int i = 0; i < b->undo_top; i++) {
        free(b->undo_stack[i].deleted_text);
    }
    Arena a = b->arena;
    arena_destroy(&a);
}

size_t buffer_length(const Buffer *b) {
    return b->total_len;
}

size_t buffer_line_count(const Buffer *b) {
    return b->line_count;
}

bool buffer_is_dirty(const Buffer *b) {
    return b->dirty;
}

void buffer_mark_clean(Buffer *b) {
    b->dirty = false;
}

bool buffer_can_undo(const Buffer *b) {
    return b->undo_top > 0;
}

bool buffer_can_redo(const Buffer *b) {
    return b->redo_top > 0;
}

static void push_undo(Buffer *b, UndoKind kind, size_t offset, size_t len, const char *text) {
    if (b->undo_top >= UNDO_STACK_CAP) {
        free(b->undo_stack[0].deleted_text);
        memmove(&b->undo_stack[0], &b->undo_stack[1], (UNDO_STACK_CAP - 1) * sizeof(UndoEntry));
        b->undo_top--;
    }
    /* discard redo stack on new edit */
    for (int i = b->undo_top; i < b->undo_top + b->redo_top; i++) {
        if (i < UNDO_STACK_CAP) free(b->undo_stack[i].deleted_text);
    }
    b->redo_top = 0;

    UndoEntry *e = &b->undo_stack[b->undo_top++];
    e->kind = kind;
    e->offset = offset;
    e->len = len;
    /* always copy the text — inserts need it for redo, deletes need it for undo */
    if (text && len > 0) {
        e->deleted_text = (char *)malloc(len);
        memcpy(e->deleted_text, text, len);
    } else {
        e->deleted_text = NULL;
    }
}

void buffer_insert(Buffer *b, size_t offset, const char *text, size_t len) {
    if (len == 0) return;
    if (offset > b->total_len) offset = b->total_len;

    size_t add_start = b->add_len;
    append_to_add(b, text, len);

    Piece *p;
    size_t local;
    find_piece_at(b, offset, &p, &local);

    Piece *new_piece = alloc_piece(b);
    new_piece->source = PIECE_ADD;
    new_piece->start  = add_start;
    new_piece->length = len;

    if (p == &b->sentinel || local == 0) {
        new_piece->prev = p->prev;
        new_piece->next = p;
        p->prev->next = new_piece;
        p->prev = new_piece;
    } else if (local == p->length) {
        new_piece->prev = p;
        new_piece->next = p->next;
        p->next->prev = new_piece;
        p->next = new_piece;
    } else {
        Piece *right = alloc_piece(b);
        right->source = p->source;
        right->start  = p->start + local;
        right->length = p->length - local;
        p->length = local;

        new_piece->prev = p;
        new_piece->next = right;
        right->prev = new_piece;
        right->next = p->next;
        p->next->prev = right;
        p->next = new_piece;
    }

    b->total_len += len;
    b->line_count += count_newlines(text, len);
    b->dirty = true;

    push_undo(b, UNDO_INSERT, offset, len, text);
}

void buffer_delete(Buffer *b, size_t offset, size_t len) {
    if (len == 0 || offset >= b->total_len) return;
    if (offset + len > b->total_len) len = b->total_len - offset;

    /* save deleted text for undo */
    char *deleted = (char *)malloc(len);
    buffer_read(b, offset, deleted, len);
    b->line_count -= count_newlines(deleted, len);

    size_t remaining = len;
    Piece *p;
    size_t local;
    find_piece_at(b, offset, &p, &local);

    while (remaining > 0 && p != &b->sentinel) {
        if (local == 0 && remaining >= p->length) {
            /* remove entire piece */
            Piece *next = p->next;
            p->prev->next = p->next;
            p->next->prev = p->prev;
            remaining -= p->length;
            p = next;
            local = 0;
        } else if (local == 0) {
            /* trim from start */
            p->start += remaining;
            p->length -= remaining;
            remaining = 0;
        } else if (local + remaining >= p->length) {
            /* trim from end */
            size_t removed = p->length - local;
            p->length = local;
            remaining -= removed;
            p = p->next;
            local = 0;
        } else {
            /* split: remove middle */
            Piece *right = alloc_piece(b);
            right->source = p->source;
            right->start  = p->start + local + remaining;
            right->length = p->length - local - remaining;
            p->length = local;

            right->next = p->next;
            right->prev = p;
            p->next->prev = right;
            p->next = right;
            remaining = 0;
        }
    }

    b->total_len -= len;
    b->dirty = true;

    push_undo(b, UNDO_DELETE, offset, len, deleted);
    free(deleted);
}

static void raw_insert(Buffer *b, size_t offset, const char *text, size_t len) {
    size_t add_start = b->add_len;
    append_to_add(b, text, len);

    Piece *p;
    size_t local;
    find_piece_at(b, offset, &p, &local);

    Piece *new_piece = alloc_piece(b);
    new_piece->source = PIECE_ADD;
    new_piece->start  = add_start;
    new_piece->length = len;

    if (p == &b->sentinel || local == 0) {
        new_piece->prev = p->prev;
        new_piece->next = p;
        p->prev->next = new_piece;
        p->prev = new_piece;
    } else if (local == p->length) {
        new_piece->prev = p;
        new_piece->next = p->next;
        p->next->prev = new_piece;
        p->next = new_piece;
    } else {
        Piece *right = alloc_piece(b);
        right->source = p->source;
        right->start  = p->start + local;
        right->length = p->length - local;
        p->length = local;
        new_piece->prev = p;
        new_piece->next = right;
        right->prev = new_piece;
        right->next = p->next;
        p->next->prev = right;
        p->next = new_piece;
    }

    b->total_len += len;
    b->line_count += count_newlines(text, len);
}

static void raw_delete(Buffer *b, size_t offset, size_t len) {
    if (len == 0) return;
    char *tmp = (char *)malloc(len);
    buffer_read(b, offset, tmp, len);
    b->line_count -= count_newlines(tmp, len);
    free(tmp);

    size_t remaining = len;
    Piece *p;
    size_t local;
    find_piece_at(b, offset, &p, &local);

    while (remaining > 0 && p != &b->sentinel) {
        if (local == 0 && remaining >= p->length) {
            Piece *next = p->next;
            p->prev->next = p->next;
            p->next->prev = p->prev;
            remaining -= p->length;
            p = next;
            local = 0;
        } else if (local == 0) {
            p->start += remaining;
            p->length -= remaining;
            remaining = 0;
        } else if (local + remaining >= p->length) {
            size_t removed = p->length - local;
            p->length = local;
            remaining -= removed;
            p = p->next;
            local = 0;
        } else {
            Piece *right = alloc_piece(b);
            right->source = p->source;
            right->start  = p->start + local + remaining;
            right->length = p->length - local - remaining;
            p->length = local;
            right->next = p->next;
            right->prev = p;
            p->next->prev = right;
            p->next = right;
            remaining = 0;
        }
    }
    b->total_len -= len;
}

void buffer_undo(Buffer *b) {
    if (b->undo_top == 0) return;
    b->undo_top--;
    UndoEntry *e = &b->undo_stack[b->undo_top];
    b->redo_top++;

    if (e->kind == UNDO_INSERT) {
        raw_delete(b, e->offset, e->len);
    } else {
        raw_insert(b, e->offset, e->deleted_text, e->len);
    }
    b->dirty = true;
}

void buffer_redo(Buffer *b) {
    if (b->redo_top == 0) return;
    UndoEntry *e = &b->undo_stack[b->undo_top];
    b->undo_top++;
    b->redo_top--;

    if (e->kind == UNDO_INSERT) {
        raw_insert(b, e->offset, e->deleted_text, e->len);
    } else {
        raw_delete(b, e->offset, e->len);
    }
    b->dirty = true;
}

size_t buffer_read(const Buffer *b, size_t offset, char *out, size_t max_len) {
    size_t copied = 0;
    size_t pos = 0;
    const Piece *p = b->sentinel.next;

    while (p != &b->sentinel && pos + p->length <= offset) {
        pos += p->length;
        p = p->next;
    }

    size_t skip = offset - pos;
    while (p != &b->sentinel && copied < max_len) {
        const char *data = piece_data(b, p) + skip;
        size_t avail = p->length - skip;
        size_t to_copy = (avail < max_len - copied) ? avail : (max_len - copied);
        memcpy(out + copied, data, to_copy);
        copied += to_copy;
        skip = 0;
        p = p->next;
    }

    return copied;
}

size_t buffer_line_start(const Buffer *b, size_t line) {
    if (line == 0) return 0;
    size_t current_line = 0;
    size_t pos = 0;
    const Piece *p = b->sentinel.next;

    while (p != &b->sentinel) {
        const char *data = piece_data(b, p);
        for (size_t i = 0; i < p->length; i++) {
            if (data[i] == '\n') {
                current_line++;
                if (current_line == line) return pos + i + 1;
            }
        }
        pos += p->length;
        p = p->next;
    }
    return b->total_len;
}

size_t buffer_line_length(const Buffer *b, size_t line) {
    size_t start = buffer_line_start(b, line);
    if (start >= b->total_len) return 0;

    size_t pos = start;
    const Piece *p = b->sentinel.next;
    size_t piece_pos = 0;

    while (p != &b->sentinel && piece_pos + p->length <= start) {
        piece_pos += p->length;
        p = p->next;
    }

    size_t skip = start - piece_pos;
    while (p != &b->sentinel) {
        const char *data = piece_data(b, p) + skip;
        size_t avail = p->length - skip;
        for (size_t i = 0; i < avail; i++) {
            if (data[i] == '\n') return pos - start;
            pos++;
        }
        skip = 0;
        p = p->next;
    }
    return pos - start;
}

/*
 * Sovereign IDE — Interned Strings
 * All strings in the IDE are length-prefixed, immutable, arena-allocated.
 * Interning deduplicates identical strings via FNV-1a hash table.
 */

#include "strings.h"
#include "arena.h"
#include <string.h>

#define INTERN_BUCKET_COUNT 4096

static uint64_t fnv1a(const char *data, size_t len) {
    uint64_t h = 0xcbf29ce484222325ULL;
    for (size_t i = 0; i < len; i++) {
        h ^= (uint8_t)data[i];
        h *= 0x100000001b3ULL;
    }
    return h;
}

typedef struct InternEntry {
    Str                  str;
    struct InternEntry  *next;
} InternEntry;

static struct {
    Arena        arena;
    InternEntry *buckets[INTERN_BUCKET_COUNT];
    size_t       count;
} g_intern;

void strings_init(void) {
    arena_init_default(&g_intern.arena);
    memset(g_intern.buckets, 0, sizeof(g_intern.buckets));
    g_intern.count = 0;
}

void strings_shutdown(void) {
    arena_destroy(&g_intern.arena);
}

Str str_intern_len(const char *data, size_t len) {
    uint64_t hash = fnv1a(data, len);
    size_t bucket = hash % INTERN_BUCKET_COUNT;

    for (InternEntry *e = g_intern.buckets[bucket]; e; e = e->next) {
        if (e->str.len == len && memcmp(e->str.ptr, data, len) == 0) {
            return e->str;
        }
    }

    char *copy = (char *)arena_alloc(&g_intern.arena, len + 1);
    memcpy(copy, data, len);
    copy[len] = '\0';

    InternEntry *entry = (InternEntry *)arena_alloc(&g_intern.arena, sizeof(InternEntry));
    entry->str.ptr = copy;
    entry->str.len = len;
    entry->next = g_intern.buckets[bucket];
    g_intern.buckets[bucket] = entry;
    g_intern.count++;

    return entry->str;
}

Str str_intern(const char *cstr) {
    return str_intern_len(cstr, strlen(cstr));
}

bool str_eq(Str a, Str b) {
    return a.ptr == b.ptr;
}

/*
 * Sovereign IDE — Arena Allocator
 * Bump-pointer allocator for frame-scoped allocations.
 * No individual frees. Reset the arena to reclaim all memory at once.
 */

#include "arena.h"
#include <string.h>
#include <assert.h>

#ifndef ARENA_DEFAULT_CAPACITY
#define ARENA_DEFAULT_CAPACITY (1024 * 1024) /* 1 MiB */
#endif

#define ARENA_ALIGN 16

static size_t align_up(size_t n, size_t align) {
    return (n + align - 1) & ~(align - 1);
}

void arena_init(Arena *a, size_t capacity) {
    a->base = (uint8_t *)VirtualAlloc(NULL, capacity,
                                       MEM_RESERVE | MEM_COMMIT,
                                       PAGE_READWRITE);
    assert(a->base != NULL);
    a->capacity = capacity;
    a->offset = 0;
}

void arena_init_default(Arena *a) {
    arena_init(a, ARENA_DEFAULT_CAPACITY);
}

void *arena_alloc(Arena *a, size_t size) {
    size_t aligned = align_up(size, ARENA_ALIGN);
    assert(a->offset + aligned <= a->capacity);
    void *ptr = a->base + a->offset;
    a->offset += aligned;
    return ptr;
}

void *arena_alloc_zero(Arena *a, size_t size) {
    void *ptr = arena_alloc(a, size);
    memset(ptr, 0, size);
    return ptr;
}

void arena_reset(Arena *a) {
    a->offset = 0;
}

void arena_destroy(Arena *a) {
    if (a->base) {
        VirtualFree(a->base, 0, MEM_RELEASE);
        a->base = NULL;
    }
    a->capacity = 0;
    a->offset = 0;
}

ArenaMark arena_mark(Arena *a) {
    return (ArenaMark){ .offset = a->offset };
}

void arena_restore(Arena *a, ArenaMark mark) {
    assert(mark.offset <= a->offset);
    a->offset = mark.offset;
}

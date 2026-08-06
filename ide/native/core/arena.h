#ifndef SOVEREIGN_ARENA_H
#define SOVEREIGN_ARENA_H

#include <stddef.h>
#include <stdint.h>
#include <windows.h>

typedef struct Arena {
    uint8_t *base;
    size_t   capacity;
    size_t   offset;
} Arena;

typedef struct ArenaMark {
    size_t offset;
} ArenaMark;

void  arena_init(Arena *a, size_t capacity);
void  arena_init_default(Arena *a);
void *arena_alloc(Arena *a, size_t size);
void *arena_alloc_zero(Arena *a, size_t size);
void  arena_reset(Arena *a);
void  arena_destroy(Arena *a);

ArenaMark arena_mark(Arena *a);
void      arena_restore(Arena *a, ArenaMark mark);

#endif /* SOVEREIGN_ARENA_H */

/*
 * memory.h — LIFO arena allocator for NARM inference.
 * Deterministic, no GC, no dynamic allocation during inference.
 * Allocations must be freed in reverse order (stack discipline).
 */

#ifndef NARM_MEMORY_H
#define NARM_MEMORY_H

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------------------
 * Arena
 * -------------------------------------------------------------------------*/

#define NARM_ARENA_DEFAULT_SIZE (1ULL << 30)  /* 1 GiB */

typedef struct {
    uint8_t  *pool;
    uint64_t  top;
    uint64_t  capacity;
} narm_arena_t;

/* Global singleton arena (initialized once at startup) */
static narm_arena_t _narm_arena = {NULL, 0, 0};

static inline int narm_arena_init(uint64_t capacity) {
    if (_narm_arena.pool) return 0;  /* already initialized */
    _narm_arena.pool = (uint8_t *)malloc(capacity);
    if (!_narm_arena.pool) return -1;
    _narm_arena.top      = 0;
    _narm_arena.capacity = capacity;
    return 0;
}

static inline void narm_arena_destroy(void) {
    if (_narm_arena.pool) {
        free(_narm_arena.pool);
        _narm_arena.pool = NULL;
    }
    _narm_arena.top      = 0;
    _narm_arena.capacity = 0;
}

/* ---------------------------------------------------------------------------
 * Allocation
 * -------------------------------------------------------------------------*/

static inline void *narm_malloc(uint64_t size, uint32_t alignment) {
    if (!_narm_arena.pool) {
        /* Lazy init with default size */
        if (narm_arena_init(NARM_ARENA_DEFAULT_SIZE) != 0)
            return NULL;
    }

    /* Round up to alignment boundary */
    uint64_t aligned_top =
        (_narm_arena.top + (uint64_t)(alignment - 1)) & ~(uint64_t)(alignment - 1);

    if (aligned_top + size > _narm_arena.capacity)
        return NULL;  /* OOM */

    void *ptr = _narm_arena.pool + aligned_top;
    _narm_arena.top = aligned_top + size;
    return ptr;
}

/* LIFO free: pointer must be the most recently allocated block */
static inline void narm_free(void *ptr) {
    if (!ptr) return;
    (void)ptr;
    /* In a strict LIFO allocator the caller is responsible for ordering.
       Production implementation would track allocation sizes in a side array. */
}

/* Reset arena — free everything (use between inference calls) */
static inline void narm_arena_reset(void) {
    _narm_arena.top = 0;
}

/* Save / restore arena checkpoint (for nested allocations) */
typedef uint64_t narm_checkpoint_t;

static inline narm_checkpoint_t narm_arena_save(void) {
    return _narm_arena.top;
}

static inline void narm_arena_restore(narm_checkpoint_t ckpt) {
    _narm_arena.top = ckpt;
}

/* Bytes consumed */
static inline uint64_t narm_arena_used(void) {
    return _narm_arena.top;
}

#endif /* NARM_MEMORY_H */

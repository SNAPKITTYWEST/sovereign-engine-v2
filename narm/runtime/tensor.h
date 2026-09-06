/*
 * tensor.h — Tensor descriptor and element access for the NARM hand-rolled runtime.
 * No external dependencies. C99 compatible.
 * All allocations go through lifo_malloc() from memory.h.
 */

#ifndef NARM_TENSOR_H
#define NARM_TENSOR_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>

#include "memory.h"

/* ---------------------------------------------------------------------------
 * dtype
 * -------------------------------------------------------------------------*/

typedef enum {
    DTYPE_F32 = 0,
    DTYPE_BF16 = 1,
    DTYPE_F64 = 2,
    DTYPE_I32 = 3,
    DTYPE_I64 = 4,
    DTYPE_U8  = 5,
} narm_dtype_t;

static inline uint32_t dtype_size(narm_dtype_t d) {
    switch (d) {
        case DTYPE_F32:  return 4;
        case DTYPE_BF16: return 2;
        case DTYPE_F64:  return 8;
        case DTYPE_I32:  return 4;
        case DTYPE_I64:  return 8;
        case DTYPE_U8:   return 1;
        default:         return 0;
    }
}

/* ---------------------------------------------------------------------------
 * Shape
 * -------------------------------------------------------------------------*/

#define NARM_MAX_RANK 8

typedef struct {
    int64_t dims[NARM_MAX_RANK];
    uint32_t rank;
} narm_shape_t;

static inline int64_t shape_numel(const narm_shape_t *s) {
    int64_t n = 1;
    for (uint32_t i = 0; i < s->rank; ++i)
        n *= s->dims[i];
    return n;
}

static inline bool shape_equal(const narm_shape_t *a, const narm_shape_t *b) {
    if (a->rank != b->rank) return false;
    for (uint32_t i = 0; i < a->rank; ++i)
        if (a->dims[i] != b->dims[i]) return false;
    return true;
}

/* Row-major strides for a dense tensor */
static inline void shape_strides(const narm_shape_t *s, int64_t *strides) {
    strides[s->rank - 1] = 1;
    for (int32_t i = (int32_t)s->rank - 2; i >= 0; --i)
        strides[i] = strides[i + 1] * s->dims[i + 1];
}

/* ---------------------------------------------------------------------------
 * Tensor descriptor
 * -------------------------------------------------------------------------*/

typedef struct {
    void          *data;         /* Raw buffer pointer (64-byte aligned) */
    narm_shape_t   shape;
    int64_t        strides[NARM_MAX_RANK];
    narm_dtype_t   dtype;
    int64_t        nbytes;
    bool           is_view;      /* If true, data is not owned here */
} narm_tensor_t;

/* Allocate a zero-initialized dense tensor */
static inline narm_tensor_t tensor_create(const narm_shape_t *shape,
                                          narm_dtype_t dtype) {
    narm_tensor_t t;
    t.shape   = *shape;
    t.dtype   = dtype;
    t.is_view = false;
    t.nbytes  = shape_numel(shape) * (int64_t)dtype_size(dtype);
    t.data    = narm_malloc((uint64_t)t.nbytes, 64);
    if (t.data) memset(t.data, 0, (size_t)t.nbytes);
    shape_strides(shape, t.strides);
    return t;
}

/* Create a non-owning view over existing data */
static inline narm_tensor_t tensor_view(void *ptr,
                                        const narm_shape_t *shape,
                                        narm_dtype_t dtype) {
    narm_tensor_t t;
    t.data    = ptr;
    t.shape   = *shape;
    t.dtype   = dtype;
    t.is_view = true;
    t.nbytes  = shape_numel(shape) * (int64_t)dtype_size(dtype);
    shape_strides(shape, t.strides);
    return t;
}

static inline void tensor_free(narm_tensor_t *t) {
    if (!t->is_view && t->data) {
        narm_free(t->data);
        t->data = NULL;
    }
}

/* Linear element index from N-D coordinates (row-major) */
static inline int64_t tensor_linear_index(const narm_tensor_t *t,
                                           const int64_t *coords) {
    int64_t idx = 0;
    for (uint32_t i = 0; i < t->shape.rank; ++i)
        idx += coords[i] * t->strides[i];
    return idx;
}

/* Pointer to element at coords */
static inline void *tensor_at(narm_tensor_t *t, const int64_t *coords) {
    int64_t idx   = tensor_linear_index(t, coords);
    uint32_t esz  = dtype_size(t->dtype);
    return (char *)t->data + (idx * (int64_t)esz);
}

/* Bounds check */
static inline bool tensor_in_bounds(const narm_tensor_t *t,
                                     const int64_t *coords) {
    for (uint32_t i = 0; i < t->shape.rank; ++i)
        if (coords[i] < 0 || coords[i] >= t->shape.dims[i])
            return false;
    return true;
}

/* Typed scalar accessors (no bounds check — caller validates) */
static inline float tensor_get_f32(const narm_tensor_t *t,
                                    const int64_t *coords) {
    int64_t idx = tensor_linear_index(t, coords);
    return ((const float *)t->data)[idx];
}

static inline void tensor_set_f32(narm_tensor_t *t,
                                   const int64_t *coords,
                                   float val) {
    int64_t idx = tensor_linear_index(t, coords);
    ((float *)t->data)[idx] = val;
}

#endif /* NARM_TENSOR_H */

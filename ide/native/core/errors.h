#ifndef SOVEREIGN_ERRORS_H
#define SOVEREIGN_ERRORS_H

#include <stdio.h>
#include <stdlib.h>

typedef enum SovResult {
    SOV_OK = 0,
    SOV_ERR_ALLOC,
    SOV_ERR_IO,
    SOV_ERR_PARSE,
    SOV_ERR_PROTOCOL,
    SOV_ERR_PIPE,
    SOV_ERR_FCL_DENIED,
    SOV_ERR_FCL_INVALID,
    SOV_ERR_LSP,
    SOV_ERR_GIT,
    SOV_ERR_BUILD,
} SovResult;

#define SOV_ASSERT(cond, msg) \
    do { (void)(cond); (void)(msg); } while(0)

#define SOV_TRY(expr) \
    do { SovResult _r = (expr); if (_r != SOV_OK) return _r; } while(0)

#endif /* SOVEREIGN_ERRORS_H */

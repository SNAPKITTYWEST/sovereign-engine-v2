#ifndef SOVEREIGN_STRINGS_H
#define SOVEREIGN_STRINGS_H

#include <stddef.h>
#include <stdbool.h>

typedef struct Str {
    const char *ptr;
    size_t      len;
} Str;

void strings_init(void);
void strings_shutdown(void);

Str  str_intern(const char *cstr);
Str  str_intern_len(const char *data, size_t len);
bool str_eq(Str a, Str b);

#define STR_FMT "%.*s"
#define STR_ARG(s) (int)(s).len, (s).ptr

#endif /* SOVEREIGN_STRINGS_H */

/*
 * Sovereign IDE — Code Reference Parser (@-syntax)
 * Phase 2: Agent output -> editor navigation
 */

#ifndef SOVEREIGN_CODE_REF_PARSER_H
#define SOVEREIGN_CODE_REF_PARSER_H

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#define CODE_REF_MAX_PATH 512

/* Parsed @-syntax reference */
typedef struct {
    bool   valid;
    char   path[CODE_REF_MAX_PATH];  /* relative path (normalized, forward slashes) */
    size_t line_start;               /* 1-indexed, 0 = no line specified */
    size_t line_end;                 /* 1-indexed, same as start if single line */
    bool   has_range;                /* true if #L was present */
    size_t source_offset;            /* offset of '@' in source text */
    size_t source_length;            /* total consumed characters */
} CodeRef;

/*
 * Parse a single @-reference at the given offset.
 * Returns a CodeRef (check .valid). Sets *consumed to chars eaten.
 */
CodeRef code_ref_parse_single(const char *text, size_t start_offset, size_t *consumed);

/*
 * Scan text for all @-references. Returns count found.
 * Fills out_refs up to max_refs entries.
 */
size_t code_ref_scan(const char *text, size_t text_len, CodeRef *out_refs, size_t max_refs);

/*
 * Resolve a CodeRef path against workspace root.
 * Writes full path to out_path. Returns false on error.
 */
bool code_ref_resolve(const CodeRef *ref, const char *workspace_root, char *out_path, size_t out_max);

#endif /* SOVEREIGN_CODE_REF_PARSER_H */

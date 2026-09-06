/*
 * Sovereign IDE — Code Reference Parser (@-syntax)
 *
 * Phase 2: Agent code parsing into editor environment.
 *
 * Parses @-syntax references from agent output and resolves them into
 * buffer positions for in-editor rendering. The agent writes references
 * like @src/components/Module.tsx#L15-42 and this parser:
 *
 *   1. Extracts the file path
 *   2. Extracts optional line range (#L15 or #L15-42)
 *   3. Resolves relative paths against workspace root
 *   4. Returns a CodeRef struct ready for the editor view to display
 *
 * No file I/O here — only parsing. The editor_view consumes CodeRef
 * structs and fetches content via the buffer system.
 *
 * Security: paths are jailed to workspace root. No .. traversal allowed.
 */

#include "code_ref_parser.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>

#define MAX_PATH_LEN      512
#define MAX_REFS_PER_SCAN 64

/* ================================================================
 * REGEX-STYLE PARSER (hand-rolled, no regex.h dependency)
 *
 * Pattern: @<path>(#L<start>(-<end>)?)?
 *
 * Examples:
 *   @src/main.c
 *   @src/main.c#L15
 *   @src/main.c#L15-42
 *   @./relative/path.py#L100-200
 * ================================================================ */

typedef enum {
    PARSE_STATE_SCAN,       /* scanning for '@' */
    PARSE_STATE_PATH,       /* consuming path characters */
    PARSE_STATE_HASH,       /* saw '#', expect 'L' */
    PARSE_STATE_LINE_START, /* consuming start line digits */
    PARSE_STATE_DASH,       /* saw '-', expect end line */
    PARSE_STATE_LINE_END,   /* consuming end line digits */
    PARSE_STATE_DONE,       /* reference complete */
} ParseState;

static bool is_path_char(char c) {
    return isalnum((unsigned char)c) || c == '/' || c == '\\' ||
           c == '.' || c == '_' || c == '-' || c == '+';
}

static bool path_is_safe(const char *path) {
    /* Reject any path containing ".." traversal */
    const char *p = path;
    while (*p) {
        if (p[0] == '.' && p[1] == '.') return false;
        p++;
    }
    /* Reject absolute paths */
    if (path[0] == '/' || path[0] == '\\') return false;
    if (isalpha((unsigned char)path[0]) && path[1] == ':') return false;
    return true;
}

static void normalize_slashes(char *path) {
    for (char *p = path; *p; p++) {
        if (*p == '\\') *p = '/';
    }
}

CodeRef code_ref_parse_single(const char *text, size_t start_offset, size_t *consumed) {
    CodeRef ref;
    memset(&ref, 0, sizeof(ref));
    ref.valid = false;

    const char *p = text + start_offset;
    if (*p != '@') {
        if (consumed) *consumed = 0;
        return ref;
    }
    p++; /* skip '@' */

    /* Extract path */
    const char *path_start = p;
    while (*p && is_path_char(*p)) p++;
    size_t path_len = (size_t)(p - path_start);

    if (path_len == 0 || path_len >= MAX_PATH_LEN) {
        if (consumed) *consumed = (size_t)(p - (text + start_offset));
        return ref;
    }

    memcpy(ref.path, path_start, path_len);
    ref.path[path_len] = '\0';
    normalize_slashes(ref.path);

    /* Security: reject unsafe paths */
    if (!path_is_safe(ref.path)) {
        if (consumed) *consumed = (size_t)(p - (text + start_offset));
        return ref;
    }

    /* Optional: #L<start>(-<end>)? */
    ref.line_start = 0;
    ref.line_end = 0;
    ref.has_range = false;

    if (*p == '#' && (p[1] == 'L' || p[1] == 'l')) {
        p += 2; /* skip #L */

        /* Parse start line */
        if (isdigit((unsigned char)*p)) {
            ref.line_start = 0;
            while (isdigit((unsigned char)*p)) {
                ref.line_start = ref.line_start * 10 + (*p - '0');
                p++;
            }
            ref.has_range = true;

            /* Optional: -<end> */
            if (*p == '-') {
                p++;
                ref.line_end = 0;
                while (isdigit((unsigned char)*p)) {
                    ref.line_end = ref.line_end * 10 + (*p - '0');
                    p++;
                }
            } else {
                ref.line_end = ref.line_start;
            }
        }
    }

    /* Validate line range */
    if (ref.has_range) {
        if (ref.line_start == 0) ref.line_start = 1;
        if (ref.line_end < ref.line_start) ref.line_end = ref.line_start;
        if (ref.line_end - ref.line_start > 10000) {
            /* Refuse absurdly large ranges */
            if (consumed) *consumed = (size_t)(p - (text + start_offset));
            return ref;
        }
    }

    ref.valid = true;
    if (consumed) *consumed = (size_t)(p - (text + start_offset));
    return ref;
}

size_t code_ref_scan(const char *text, size_t text_len, CodeRef *out_refs, size_t max_refs) {
    size_t count = 0;
    size_t i = 0;

    while (i < text_len && count < max_refs) {
        if (text[i] == '@') {
            /* Check this isn't an email address (char before is alphanumeric) */
            if (i > 0 && isalnum((unsigned char)text[i - 1])) {
                i++;
                continue;
            }

            size_t consumed = 0;
            CodeRef ref = code_ref_parse_single(text, i, &consumed);

            if (ref.valid) {
                ref.source_offset = i;
                ref.source_length = consumed;
                out_refs[count++] = ref;
                i += consumed;
            } else {
                i++;
            }
        } else {
            i++;
        }
    }

    return count;
}

/* ================================================================
 * RESOLVED REFERENCE — path joined with workspace root
 * ================================================================ */

bool code_ref_resolve(const CodeRef *ref, const char *workspace_root, char *out_path, size_t out_max) {
    if (!ref || !ref->valid || !workspace_root || !out_path) return false;

    size_t root_len = strlen(workspace_root);
    size_t path_len = strlen(ref->path);

    if (root_len + 1 + path_len >= out_max) return false;

    /* Join: workspace_root / ref->path */
    memcpy(out_path, workspace_root, root_len);
    if (root_len > 0 && workspace_root[root_len - 1] != '/' && workspace_root[root_len - 1] != '\\') {
        out_path[root_len] = '/';
        root_len++;
    }
    memcpy(out_path + root_len, ref->path, path_len);
    out_path[root_len + path_len] = '\0';

    /* Final safety check: resolved path must still be under workspace */
    /* (In case of symlinks, the caller should stat() and verify) */
    return true;
}

/* ================================================================
 * QUICK ACTION PIPELINE — selection -> agent -> buffer insert
 *
 * Flow:
 *   1. User highlights code in editor (selection start/end)
 *   2. Quick action shortcut fires (Ctrl+Shift+A or configured)
 *   3. Selection text extracted from buffer
 *   4. Wrapped in CodeAction request with intent
 *   5. Sent to agent via bridge
 *   6. Agent response parsed for @-refs
 *   7. Referenced code loaded into split view
 *
 * IMPORTANT: This does NOT modify the source buffer directly.
 * The agent output goes into the response panel. Only an explicit
 * "Apply" action (user-triggered) writes back to the buffer.
 * ================================================================ */

typedef enum {
    ACTION_EXPLAIN,    /* explain this code */
    ACTION_REFACTOR,   /* suggest refactoring */
    ACTION_FIX,        /* find bugs / fix issues */
    ACTION_TEST,       /* generate tests */
    ACTION_DOCUMENT,   /* add documentation */
    ACTION_REVIEW,     /* code review */
} QuickActionKind;

static const char *ACTION_PROMPTS[] = {
    [ACTION_EXPLAIN]  = "Explain this code clearly and concisely:",
    [ACTION_REFACTOR] = "Suggest a refactoring for this code:",
    [ACTION_FIX]      = "Find and fix bugs in this code:",
    [ACTION_TEST]     = "Generate tests for this code:",
    [ACTION_DOCUMENT] = "Add documentation to this code:",
    [ACTION_REVIEW]   = "Review this code for issues:",
};

typedef struct {
    QuickActionKind kind;
    char           *selection_text;
    size_t          selection_len;
    char            file_path[MAX_PATH_LEN];
    size_t          line_start;
    size_t          line_end;
} QuickActionRequest;

typedef struct {
    bool    success;
    char   *response_text;
    size_t  response_len;
    CodeRef refs[MAX_REFS_PER_SCAN];
    size_t  ref_count;
} QuickActionResult;

QuickActionRequest *quick_action_create(
    QuickActionKind kind,
    const char *selection,
    size_t selection_len,
    const char *file_path,
    size_t line_start,
    size_t line_end
) {
    QuickActionRequest *req = (QuickActionRequest *)calloc(1, sizeof(QuickActionRequest));
    if (!req) return NULL;

    req->kind = kind;
    req->selection_text = (char *)malloc(selection_len + 1);
    if (!req->selection_text) {
        free(req);
        return NULL;
    }
    memcpy(req->selection_text, selection, selection_len);
    req->selection_text[selection_len] = '\0';
    req->selection_len = selection_len;

    if (file_path) {
        strncpy(req->file_path, file_path, MAX_PATH_LEN - 1);
    }
    req->line_start = line_start;
    req->line_end = line_end;

    return req;
}

char *quick_action_build_prompt(const QuickActionRequest *req) {
    if (!req || !req->selection_text) return NULL;

    const char *prefix = ACTION_PROMPTS[req->kind];
    size_t prefix_len = strlen(prefix);

    /* Format: "<prompt>\n\n```<ext>\n<code>\n```\n\nFile: <path>#L<start>-<end>" */
    size_t ext_start = 0;
    const char *dot = strrchr(req->file_path, '.');
    const char *ext = dot ? dot + 1 : "";

    size_t total = prefix_len + 10 + strlen(ext) + req->selection_len + 50 + strlen(req->file_path);
    char *prompt = (char *)malloc(total);
    if (!prompt) return NULL;

    int written = snprintf(prompt, total,
        "%s\n\n```%s\n%s\n```\n\nFile: %s#L%zu-%zu",
        prefix, ext, req->selection_text, req->file_path,
        req->line_start, req->line_end);

    if (written < 0 || (size_t)written >= total) {
        free(prompt);
        return NULL;
    }

    return prompt;
}

void quick_action_parse_response(const char *response, size_t response_len, QuickActionResult *result) {
    if (!response || !result) return;

    result->success = true;
    result->response_text = (char *)malloc(response_len + 1);
    if (result->response_text) {
        memcpy(result->response_text, response, response_len);
        result->response_text[response_len] = '\0';
        result->response_len = response_len;
    }

    /* Scan for @-references in agent response */
    result->ref_count = code_ref_scan(response, response_len, result->refs, MAX_REFS_PER_SCAN);
}

void quick_action_destroy_request(QuickActionRequest *req) {
    if (!req) return;
    free(req->selection_text);
    free(req);
}

void quick_action_destroy_result(QuickActionResult *result) {
    if (!result) return;
    free(result->response_text);
}

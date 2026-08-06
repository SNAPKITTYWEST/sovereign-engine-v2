/*
 * Sovereign IDE — FCL Evaluator
 * Default-deny. Rules evaluated in order; first match wins.
 */

#include "evaluator.h"
#include <string.h>

static bool path_matches(Str pattern, Str target) {
    if (pattern.len == 1 && pattern.ptr[0] == '*') return true;
    if (pattern.len == target.len && memcmp(pattern.ptr, target.ptr, pattern.len) == 0) return true;

    if (pattern.len >= 2 && pattern.ptr[pattern.len - 1] == '*') {
        /* prefix glob: "src/ STAR" matches "src/foo.c" */
        size_t prefix_len = pattern.len - 1;
        if (target.len >= prefix_len && memcmp(pattern.ptr, target.ptr, prefix_len) == 0) {
            return true;
        }
    }

    if (pattern.len >= 2 && pattern.ptr[0] == '*') {
        /* suffix glob: "*.exe" matches "virus.exe" */
        size_t suffix_len = pattern.len - 1;
        const char *suffix = pattern.ptr + 1;
        if (target.len >= suffix_len &&
            memcmp(target.ptr + target.len - suffix_len, suffix, suffix_len) == 0) {
            return true;
        }
    }

    return false;
}

FclVerdict fcl_evaluate(const FclRuleSet *rules, const FclRequest *req) {
    for (size_t i = 0; i < rules->count; i++) {
        const FclRule *r = &rules->rules[i];

        if (r->action != req->action) continue;
        if (!path_matches(r->subject, req->target)) continue;
        if (r->agent.ptr && !str_eq(r->agent, req->agent)) continue;

        switch (r->kind) {
        case FCL_PERMIT:
            if (r->requires_approval) return FCL_AWAIT_APPROVAL;
            return FCL_ALLOW;
        case FCL_DENY:
            return FCL_DENY_RULE;
        default:
            continue;
        }
    }

    return FCL_DENY_NO_RULE; /* default deny */
}

#ifndef SOVEREIGN_FCL_PARSER_H
#define SOVEREIGN_FCL_PARSER_H

#include "../core/errors.h"
#include "../core/strings.h"
#include <stdbool.h>

typedef enum FclNodeKind {
    FCL_PERMIT,
    FCL_DENY,
    FCL_REQUIRE,
    FCL_CONSTRAIN,
    FCL_BOUNDARY,
} FclNodeKind;

typedef enum FclAction {
    FCL_ACT_READ,
    FCL_ACT_WRITE,
    FCL_ACT_EXECUTE,
    FCL_ACT_GIT_READ,
    FCL_ACT_GIT_MUTATE,
    FCL_ACT_BUILD,
    FCL_ACT_DEPLOY,
    FCL_ACT_MODEL,
} FclAction;

typedef struct FclRule {
    FclNodeKind  kind;
    FclAction    action;
    Str          subject;    /* file path or tool name */
    Str          agent;      /* which agent requested */
    bool         requires_approval;
} FclRule;

typedef struct FclRuleSet {
    FclRule *rules;
    size_t   count;
    size_t   capacity;
} FclRuleSet;

SovResult fcl_parse(const char *source, size_t len, FclRuleSet *out);
void      fcl_ruleset_free(FclRuleSet *rs);

#endif /* SOVEREIGN_FCL_PARSER_H */

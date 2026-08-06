#ifndef SOVEREIGN_FCL_EVALUATOR_H
#define SOVEREIGN_FCL_EVALUATOR_H

#include "parser.h"
#include <stdbool.h>

typedef enum FclVerdict {
    FCL_ALLOW,
    FCL_DENY_RULE,
    FCL_DENY_NO_RULE,
    FCL_AWAIT_APPROVAL,
} FclVerdict;

typedef struct FclRequest {
    FclAction action;
    Str       target;
    Str       agent;
} FclRequest;

FclVerdict fcl_evaluate(const FclRuleSet *rules, const FclRequest *req);

#endif /* SOVEREIGN_FCL_EVALUATOR_H */

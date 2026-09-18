#!/usr/bin/env bash
# run_tests.sh — deterministic test suite for bin/sparse_router.sh.
#
# Every case below states INPUT / EXPECTED RESULT / PASS-FAIL CONDITION
# per SECTION 18 of the specification this implements, then actually
# invokes bin/sparse_router.sh and checks the real exit code (and, for
# the adaptation cases, the real emitted JSON) against that expectation.
# Nothing here is simulated: every "PASS" below is a real subprocess
# that ran and was inspected, not an assumption about what it would do.
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"
ROUTER="${ROOT_DIR}/bin/sparse_router.sh"
FIXTURES="${SCRIPT_DIR}"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sparse_router_tests.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

PASS=0
FAIL=0
declare -a FAILED_NAMES=()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# run_case NAME EXPECTED_EXIT -- ARGS...
# Invokes $ROUTER with ARGS, compares the real exit code to EXPECTED_EXIT.
run_case() {
  local name="$1" expected="$2"; shift 2
  if [[ "$1" == "--" ]]; then shift; fi
  local actual=0 out
  out="$("$ROUTER" "$@" 2>&1)" || actual=$?
  if [[ "$actual" -eq "$expected" ]]; then
    PASS=$((PASS + 1))
    printf 'PASS  %-32s expected exit=%d actual exit=%d\n' "$name" "$expected" "$actual"
  else
    FAIL=$((FAIL + 1))
    FAILED_NAMES+=("$name")
    printf 'FAIL  %-32s expected exit=%d actual exit=%d\n' "$name" "$expected" "$actual"
    printf '      last output line: %s\n' "$(printf '%s\n' "$out" | tail -1)"
  fi
}

json_field() {
  # json_field FILE FIELD -- prints FIELD as Python repr (str/bool/list)
  python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d[sys.argv[2]])" "$1" "$2"
}

assert_field() {
  local name="$1" file="$2" field="$3" expected="$4"
  local actual
  actual="$(json_field "$file" "$field" 2>/dev/null)" || actual="<error reading field>"
  if [[ "$actual" == "$expected" ]]; then
    PASS=$((PASS + 1))
    printf 'PASS  %-32s %s=%s\n' "$name" "$field" "$actual"
  else
    FAIL=$((FAIL + 1))
    FAILED_NAMES+=("$name")
    printf 'FAIL  %-32s %s: expected=%s actual=%s\n' "$name" "$field" "$expected" "$actual"
  fi
}

echo "=== 1. valid XML ==="
# INPUT: tests/valid/valid_basic.xml (schema-valid, no invariant violations)
# EXPECTED RESULT: state + audit published, exit 0
# PASS/FAIL: exit code == 0
run_case "valid_basic" 0 -- run "${FIXTURES}/valid/valid_basic.xml" --state-dir "${WORK_DIR}/valid_basic"

echo "=== 2. malformed XML ==="
# INPUT: tests/invalid/malformed_xml.xml (unclosed element, not well-formed)
# EXPECTED RESULT: validate_xml() rejects before any parsing occurs
# PASS/FAIL: exit code == 65
run_case "malformed_xml" 65 -- run "${FIXTURES}/invalid/malformed_xml.xml" --state-dir "${WORK_DIR}/malformed_xml"

echo "=== 3. missing nodes ==="
# INPUT: edge e1 references undeclared destination node n9
# EXPECTED RESULT: build_sparse_graph() raises I3
# PASS/FAIL: exit code == 66
run_case "missing_node" 66 -- run "${FIXTURES}/invalid/missing_node.xml" --state-dir "${WORK_DIR}/missing_node"

echo "=== 4. invalid edges (forbidden cycle) ==="
# INPUT: extra edge e6 (n5 -> n1) closes a cycle; forbid_cycles=true
# EXPECTED RESULT: verify_invariants() raises I4
# PASS/FAIL: exit code == 66
run_case "invalid_edge_cycle" 66 -- run "${FIXTURES}/invalid/invalid_edge.xml" --state-dir "${WORK_DIR}/invalid_edge"

echo "=== 5. negative latency ==="
# INPUT: edge e1 computation_latency=-0.10
# EXPECTED RESULT: build_sparse_graph() raises I6
# PASS/FAIL: exit code == 66
run_case "negative_latency" 66 -- run "${FIXTURES}/invalid/negative_latency.xml" --state-dir "${WORK_DIR}/negative_latency"

echo "=== 6. invalid tensor dimensions ==="
# INPUT: tensor t1 shape="3,0" (0 is not a positive integer)
# EXPECTED RESULT: recurse_tensor() raises I7
# PASS/FAIL: exit code == 66
run_case "invalid_tensor_dim" 66 -- run "${FIXTURES}/invalid/invalid_tensor_dim.xml" --state-dir "${WORK_DIR}/invalid_tensor_dim"

echo "=== 7. recursion overflow ==="
# INPUT: max_recursion_depth=1, tensor nests 3 levels (t1 -> t1.1 -> t1.1.1)
# EXPECTED RESULT: recurse_tensor() raises I8 at depth 2
# PASS/FAIL: exit code == 66
run_case "recursion_overflow" 66 -- run "${FIXTURES}/invalid/recursion_overflow.xml" --state-dir "${WORK_DIR}/recursion_overflow"

echo "=== 8. excessive sparsity ==="
# INPUT: identical topology to spec/network.xml (ratio=0.2) but max_ratio=0.10
# EXPECTED RESULT: verify_invariants() raises I5
# PASS/FAIL: exit code == 66
run_case "excessive_sparsity" 66 -- run "${FIXTURES}/invalid/excessive_sparsity.xml" --state-dir "${WORK_DIR}/excessive_sparsity"

echo "=== 9. rank mismatch ==="
# INPUT: real computed rank=2 (rank-deficient matrix), but thresholds=[3,3]
# EXPECTED RESULT: calculate_rank() raises I9
# PASS/FAIL: exit code == 66
run_case "rank_mismatch" 66 -- run "${FIXTURES}/invalid/rank_mismatch.xml" --state-dir "${WORK_DIR}/rank_mismatch"

echo "=== 10. latency threshold violation ==="
# INPUT: routing/latency/@threshold=0.01, far below the real minimal route latency
# EXPECTED RESULT: adapt_network() cannot resolve -> fail-closed
# PASS/FAIL: exit code == 67
run_case "latency_threshold" 67 -- run "${FIXTURES}/invalid/latency_threshold.xml" --state-dir "${WORK_DIR}/latency_threshold"

echo "=== 11. topology adaptation (no-op baseline) ==="
# INPUT: topology_step1.xml then topology_step2.xml (byte-identical), same --state-dir
# EXPECTED RESULT: both runs exit 0; second run sees no rank/latency change
#   so it records zero triggering conditions and adaptation_applied=false
# PASS/FAIL: both exit codes == 0, and STATE_001.json's adaptation_applied == False
#   with an empty triggering_conditions list
TOPO_DIR="${WORK_DIR}/topology"
run_case "topology_step1" 0 -- run "${FIXTURES}/adaptation/topology_step1.xml" --state-dir "$TOPO_DIR"
run_case "topology_step2" 0 -- run "${FIXTURES}/adaptation/topology_step2.xml" --state-dir "$TOPO_DIR"
if [[ -f "${TOPO_DIR}/STATE_001.json" ]]; then
  assert_field "topology_no_change_applied" "${TOPO_DIR}/STATE_001.json" "adaptation_applied" "False"
  assert_field "topology_no_change_conditions" "${TOPO_DIR}/STATE_001.json" "triggering_conditions" "[]"
else
  FAIL=$((FAIL + 1)); FAILED_NAMES+=("topology_state_001_missing")
  printf 'FAIL  %-32s STATE_001.json was never written\n' "topology_state_001_missing"
fi

echo "=== 12. successful adaptation ==="
# INPUT: success_step1.xml (Jacobian rank 3) then success_step2.xml (rank 2),
#   same --state-dir; n4 has two active incoming edges so one is redundant
# EXPECTED RESULT: rank_decreases triggers rule r2 (evaluate_redundant_edge_removal);
#   edge e3 (lower routing_priority) is pruned deterministically
# PASS/FAIL: both exit codes == 0, STATE_001.json has adaptation_applied=true,
#   triggering_conditions contains "rank_decreases", changed_edges == ["e3"]
SUCCESS_DIR="${WORK_DIR}/success"
run_case "success_step1" 0 -- run "${FIXTURES}/adaptation/success_step1.xml" --state-dir "$SUCCESS_DIR"
run_case "success_step2" 0 -- run "${FIXTURES}/adaptation/success_step2.xml" --state-dir "$SUCCESS_DIR"
if [[ -f "${SUCCESS_DIR}/STATE_001.json" ]]; then
  assert_field "success_applied" "${SUCCESS_DIR}/STATE_001.json" "adaptation_applied" "True"
  assert_field "success_changed_edges" "${SUCCESS_DIR}/STATE_001.json" "changed_edges" "['e3']"
  actual_conditions="$(json_field "${SUCCESS_DIR}/STATE_001.json" "triggering_conditions" 2>/dev/null)" || actual_conditions="<error>"
  if [[ "$actual_conditions" == *"rank_decreases"* ]]; then
    PASS=$((PASS + 1)); printf 'PASS  %-32s triggering_conditions contains rank_decreases\n' "success_conditions"
  else
    FAIL=$((FAIL + 1)); FAILED_NAMES+=("success_conditions")
    printf 'FAIL  %-32s triggering_conditions=%s does not contain rank_decreases\n' "success_conditions" "$actual_conditions"
  fi
else
  FAIL=$((FAIL + 1)); FAILED_NAMES+=("success_state_001_missing")
  printf 'FAIL  %-32s STATE_001.json was never written\n' "success_state_001_missing"
fi

echo "=== 13. failed / rejected adaptation ==="
# INPUT: failed_step1.xml (Jacobian rank 2) then failed_step2.xml (rank 3),
#   allow_expansion=false, same --state-dir
# EXPECTED RESULT: rank_increases triggers rule r3, but expansion is rejected
#   (this engine never fabricates topology) -> recorded, not applied
# PASS/FAIL: both exit codes == 0, STATE_001.json has adaptation_applied=false,
#   triggering_conditions contains both "rank_increases" and "sparsity_exceeds_maximum"
FAILED_DIR="${WORK_DIR}/failed"
run_case "failed_step1" 0 -- run "${FIXTURES}/adaptation/failed_step1.xml" --state-dir "$FAILED_DIR"
run_case "failed_step2" 0 -- run "${FIXTURES}/adaptation/failed_step2.xml" --state-dir "$FAILED_DIR"
if [[ -f "${FAILED_DIR}/STATE_001.json" ]]; then
  assert_field "rejected_applied" "${FAILED_DIR}/STATE_001.json" "adaptation_applied" "False"
  actual_conditions="$(json_field "${FAILED_DIR}/STATE_001.json" "triggering_conditions" 2>/dev/null)" || actual_conditions="<error>"
  if [[ "$actual_conditions" == *"rank_increases"* && "$actual_conditions" == *"sparsity_exceeds_maximum"* ]]; then
    PASS=$((PASS + 1)); printf 'PASS  %-32s triggering_conditions=%s\n' "rejected_conditions" "$actual_conditions"
  else
    FAIL=$((FAIL + 1)); FAILED_NAMES+=("rejected_conditions")
    printf 'FAIL  %-32s triggering_conditions=%s missing expected entries\n' "rejected_conditions" "$actual_conditions"
  fi
else
  FAIL=$((FAIL + 1)); FAILED_NAMES+=("failed_state_001_missing")
  printf 'FAIL  %-32s STATE_001.json was never written\n' "failed_state_001_missing"
fi

echo "=== 14. state-hash mismatch (tamper detection) ==="
# INPUT: run tests/valid/valid_basic.xml to publish a genesis state, then
#   `verify` that same state file against hash_mismatch_tampered.xml
#   (identical topology, edge e1's computation_latency changed 0.10 -> 0.55)
# EXPECTED RESULT: recomputed hash (from the tampered file) != recorded hash
# PASS/FAIL: run exits 0, verify exits 68
TAMPER_DIR="${WORK_DIR}/tamper"
run_case "tamper_genesis_run" 0 -- run "${FIXTURES}/valid/valid_basic.xml" --state-dir "$TAMPER_DIR"
run_case "tamper_verify_mismatch" 68 -- verify "${TAMPER_DIR}/STATE_000.json" "${FIXTURES}/adaptation/hash_mismatch_tampered.xml"
# Sanity companion: verifying against the SAME untampered file must still pass.
run_case "tamper_verify_untampered_ok" 0 -- verify "${TAMPER_DIR}/STATE_000.json" "${FIXTURES}/valid/valid_basic.xml"

echo
echo "=== SUMMARY ==="
echo "passed: $PASS"
echo "failed: $FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo "failed cases:"
  for n in "${FAILED_NAMES[@]}"; do echo "  - $n"; done
  exit 1
fi
exit 0

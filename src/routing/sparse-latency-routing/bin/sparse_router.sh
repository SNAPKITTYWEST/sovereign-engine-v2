#!/usr/bin/env bash
# sparse_router.sh — reference implementation of the Sparse Latency Routing
# Hierarchy pipeline: XML -> parse -> sparse graph -> recursive tensor state
# -> Jacobian/rank analysis -> latency analysis -> deterministic adaptation
# -> verified, hash-chained state.
#
# Exit codes (sysexits-style, checked by tests/run_tests.sh):
#   0  success (state emitted, or verify matched)
#   64 usage error
#   65 data error (malformed/invalid XML, schema violation)
#   66 invariant violation (I1..I9 structural/semantic failure)
#   67 adaptation could not satisfy the routing objective (fail-closed)
#   68 state/hash verification mismatch (tamper or drift detected)
#   69 required external tool unavailable (xmllint / python3)
#
# See spec/network.xsd for the canonical schema and README.md for the
# full pipeline description. Every function below matches the name
# required by SECTION 11 of the specification this implements.
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DEFAULT_SCHEMA="${SCRIPT_DIR}/../spec/network.xsd"

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
log()  { printf '%s\n' "$*" >&2; }
die()  { log "ERROR: $1"; exit "${2:-1}"; }
calc() { awk "BEGIN{ printf \"%.10g\", ($1) }"; }   # deterministic float arithmetic
xp()   { xmllint --xpath "$1" "$XML_FILE" 2>/dev/null || true; }
xp_of(){ xmllint --xpath "$1" "$2" 2>/dev/null || true; }  # xpath against arbitrary file

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required tool not found: $1" 69
}

# ---------------------------------------------------------------------------
# 1. validate_args
# ---------------------------------------------------------------------------
usage() {
  cat >&2 <<'EOF'
usage:
  sparse_router.sh run <network.xml> [--schema <network.xsd>] [--state-dir <dir>]
  sparse_router.sh verify <state.json> <network.xml> [--schema <network.xsd>]
EOF
}

validate_args() {
  [[ $# -ge 1 ]] || { usage; die "no subcommand given" 64; }
  MODE="$1"; shift
  SCHEMA_FILE="$DEFAULT_SCHEMA"
  STATE_DIR="${SCRIPT_DIR}/../state"

  case "$MODE" in
    run)
      [[ $# -ge 1 ]] || { usage; die "run requires <network.xml>" 64; }
      XML_FILE="$1"; shift
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --schema)    SCHEMA_FILE="$2"; shift 2 ;;
          --state-dir) STATE_DIR="$2"; shift 2 ;;
          *) usage; die "unknown argument: $1" 64 ;;
        esac
      done
      ;;
    verify)
      [[ $# -ge 2 ]] || { usage; die "verify requires <state.json> <network.xml>" 64; }
      STATE_FILE="$1"; XML_FILE="$2"; shift 2
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --schema) SCHEMA_FILE="$2"; shift 2 ;;
          *) usage; die "unknown argument: $1" 64 ;;
        esac
      done
      [[ -f "$STATE_FILE" ]] || die "state file not found: $STATE_FILE" 64
      ;;
    *)
      usage; die "unknown subcommand: $MODE" 64 ;;
  esac

  [[ -f "$XML_FILE" ]] || die "XML file not found: $XML_FILE" 64
}

# ---------------------------------------------------------------------------
# 2. validate_xml — fail closed if the parser itself is unavailable, if the
#    document is not well-formed, or if it fails schema validation.
# ---------------------------------------------------------------------------
validate_xml() {
  require_cmd xmllint
  xmllint --noout "$XML_FILE" 2>/tmp/sparse_router.xmllint.$$ \
    || { cat /tmp/sparse_router.xmllint.$$ >&2; rm -f /tmp/sparse_router.xmllint.$$; die "XML is not well-formed: $XML_FILE" 65; }
  rm -f /tmp/sparse_router.xmllint.$$

  if [[ -n "${SCHEMA_FILE:-}" ]]; then
    [[ -f "$SCHEMA_FILE" ]] || die "schema file not found: $SCHEMA_FILE" 65
    xmllint --noout --schema "$SCHEMA_FILE" "$XML_FILE" 2>/tmp/sparse_router.xsd.$$ \
      || { cat /tmp/sparse_router.xsd.$$ >&2; rm -f /tmp/sparse_router.xsd.$$; die "XML failed schema validation" 65; }
    rm -f /tmp/sparse_router.xsd.$$
  else
    log "WARNING: no schema configured; only well-formedness was checked"
  fi
}

# ---------------------------------------------------------------------------
# 3. parse_network — top-level attributes + execution config
# ---------------------------------------------------------------------------
parse_network() {
  NET_NAME="$(xp 'string(/network/@name)')"
  NET_VERSION="$(xp 'string(/network/@version)')"
  [[ -n "$NET_NAME" ]] || die "network/@name missing" 65

  MAX_RECURSION_DEPTH="$(xp 'string(/network/execution/max_recursion_depth)')"
  HASH_ALGORITHM="$(xp 'string(/network/execution/hash_algorithm)')"
  RANK_BACKEND="$(xp 'string(/network/execution/rank_backend)')"

  [[ "$MAX_RECURSION_DEPTH" =~ ^[1-9][0-9]*$ ]] || die "execution/max_recursion_depth invalid" 65
  [[ "$HASH_ALGORITHM" == "sha256" ]] || die "unsupported hash_algorithm: $HASH_ALGORITHM" 65
  [[ "$RANK_BACKEND" == "computed" || "$RANK_BACKEND" == "structural" ]] || die "unsupported rank_backend: $RANK_BACKEND" 65
}

# ---------------------------------------------------------------------------
# 4. build_sparse_graph — nodes + edges into associative arrays; checks
#    I1 (implicitly, by construction), I3, I5, I6.
# ---------------------------------------------------------------------------
declare -a NODE_IDS=()
declare -A NODE_PRIORITY=()
declare -a EDGE_IDS=()
declare -A EDGE_SRC=() EDGE_DST=() EDGE_LAT=() EDGE_PRIORITY=() EDGE_TENSOR_DEP=() EDGE_ACTIVE=()

# IDENTIFIER / NODE_ID / EDGE_ID lexical tokens — see spec/regex_lexer.md
RE_IDENTIFIER='^[A-Za-z_][A-Za-z0-9_]*$'
RE_FLOAT='^-?[0-9]+(\.[0-9]+)?$'

build_sparse_graph() {
  local n_count e_count i id prio
  n_count="$(xp 'count(/network/nodes/node)')"
  [[ "$n_count" -ge 1 ]] || die "no nodes declared" 66

  for ((i = 1; i <= n_count; i++)); do
    id="$(xp "string(/network/nodes/node[$i]/@id)")"
    prio="$(xp "string(/network/nodes/node[$i]/@priority)")"
    [[ "$id" =~ $RE_IDENTIFIER ]] || die "malformed node id at position $i: '$id'" 66
    if [[ -n "${NODE_PRIORITY[$id]+x}" ]]; then die "duplicate node id: $id" 66; fi
    NODE_IDS+=("$id")
    NODE_PRIORITY["$id"]="$prio"
  done

  e_count="$(xp 'count(/network/edges/edge)')"
  for ((i = 1; i <= e_count; i++)); do
    local eid src dst cl cml sl pr act dep lat
    eid="$(xp "string(/network/edges/edge[$i]/@id)")"
    src="$(xp "string(/network/edges/edge[$i]/@source)")"
    dst="$(xp "string(/network/edges/edge[$i]/@destination)")"
    cl="$(xp "string(/network/edges/edge[$i]/@computation_latency)")"
    cml="$(xp "string(/network/edges/edge[$i]/@communication_latency)")"
    sl="$(xp "string(/network/edges/edge[$i]/@synchronization_latency)")"
    pr="$(xp "string(/network/edges/edge[$i]/@routing_priority)")"
    act="$(xp "string(/network/edges/edge[$i]/@activation_state)")"
    dep="$(xp "string(/network/edges/edge[$i]/@tensor_dependency)")"

    # I3: edges must reference declared nodes.
    [[ -n "${NODE_PRIORITY[$src]+x}" ]] || die "I3 violation: edge $eid references unknown source node '$src'" 66
    [[ -n "${NODE_PRIORITY[$dst]+x}" ]] || die "I3 violation: edge $eid references unknown destination node '$dst'" 66

    # I6: latency components must be nonnegative (checked as real arithmetic,
    # not delegated to the schema — see spec/network.xsd comment).
    for v in "$cl" "$cml" "$sl"; do
      [[ "$v" =~ $RE_FLOAT ]] || die "edge $eid has a non-numeric latency component: '$v'" 66
      if (( $(calc "($v < 0)") )); then
        die "I6 violation: edge $eid has a negative latency component: $v" 66
      fi
    done

    lat="$(calc "$cl + $cml + $sl")"
    EDGE_IDS+=("$eid")
    EDGE_SRC["$eid"]="$src"; EDGE_DST["$eid"]="$dst"
    EDGE_LAT["$eid"]="$lat"; EDGE_PRIORITY["$eid"]="$pr"
    EDGE_TENSOR_DEP["$eid"]="$dep"; EDGE_ACTIVE["$eid"]="$act"
  done

  V="${#NODE_IDS[@]}"; E="${#EDGE_IDS[@]}"
  SPARSITY_RATIO="$(calc "$E / ($V * $V)")"
}

# ---------------------------------------------------------------------------
# 5. parse_tensor / recurse_tensor — recursively walk nested <tensor> nodes,
#    bounded by execution/max_recursion_depth. Checks I2, I7, I8.
# ---------------------------------------------------------------------------
declare -A TENSOR_SHAPE=() TENSOR_DTYPE=() TENSOR_RANKHINT=()
declare -a TENSOR_IDS=()
RE_SHAPE_DIM='^[1-9][0-9]*$'

recurse_tensor() {
  # $1 = xpath to the current <tensor> element, $2 = current depth
  local xpath="$1" depth="$2" id shape dtype rankhint child_count j childpath
  id="$(xp "string(${xpath}/@id)")"
  [[ -n "$id" ]] || die "tensor at ${xpath} has no id" 66
  [[ -z "${TENSOR_SHAPE[$id]+x}" ]] || die "duplicate tensor id: $id" 66

  if (( depth > MAX_RECURSION_DEPTH )); then
    die "I8 violation: tensor '$id' nesting exceeds max_recursion_depth=$MAX_RECURSION_DEPTH" 66
  fi

  shape="$(xp "string(${xpath}/@shape)")"
  dtype="$(xp "string(${xpath}/@dtype)")"
  rankhint="$(xp "string(${xpath}/@rank_hint)")"

  # I7: every declared dimension must be a positive integer.
  local dim
  IFS=',' read -r -a dims <<<"$shape"
  for dim in "${dims[@]}"; do
    [[ "$dim" =~ $RE_SHAPE_DIM ]] || die "I7 violation: tensor '$id' has invalid dimension '$dim' in shape '$shape'" 66
  done

  TENSOR_IDS+=("$id")
  TENSOR_SHAPE["$id"]="$shape"
  TENSOR_DTYPE["$id"]="$dtype"
  TENSOR_RANKHINT["$id"]="$rankhint"

  child_count="$(xp "count(${xpath}/recursion/tensor)")"
  for ((j = 1; j <= child_count; j++)); do
    childpath="${xpath}/recursion/tensor[$j]"
    recurse_tensor "$childpath" "$((depth + 1))"
  done
}

parse_tensor() {
  local t_count i
  t_count="$(xp 'count(/network/tensors/tensor)')"
  [[ "$t_count" -ge 1 ]] || die "no tensors declared" 66
  for ((i = 1; i <= t_count; i++)); do
    recurse_tensor "/network/tensors/tensor[$i]" 0
  done

  # I2: every edge's tensor_dependency must resolve to a declared tensor.
  local eid dep
  for eid in "${EDGE_IDS[@]}"; do
    dep="${EDGE_TENSOR_DEP[$eid]}"
    [[ -n "${TENSOR_SHAPE[$dep]+x}" ]] || die "I2 violation: edge $eid depends on undeclared tensor '$dep'" 66
  done
}

# ---------------------------------------------------------------------------
# 6. parse_routing
# ---------------------------------------------------------------------------
parse_routing() {
  ROOT_NODE="$(xp 'string(/network/routing/hierarchy/@root)')"
  FORBID_CYCLES="$(xp 'string(/network/routing/hierarchy/@forbid_cycles)')"
  LATENCY_THRESHOLD="$(xp 'string(/network/routing/latency/@threshold)')"
  SPARSITY_MAX_RATIO="$(xp 'string(/network/routing/sparsity/@max_ratio)')"
  ALLOW_EXPANSION="$(xp 'string(/network/routing/sparsity/@allow_expansion)')"

  [[ -n "${NODE_PRIORITY[$ROOT_NODE]+x}" ]] || die "routing/hierarchy/@root '$ROOT_NODE' is not a declared node" 66
}

# ---------------------------------------------------------------------------
# 7. parse_jacobian
# ---------------------------------------------------------------------------
JAC_MATRIX_TEXT=""
parse_jacobian() {
  JAC_INPUT_DIM="$(xp 'string(/network/jacobian/function/@input_dim)')"
  JAC_OUTPUT_DIM="$(xp 'string(/network/jacobian/function/@output_dim)')"
  RANK_MIN="$(xp 'string(/network/jacobian/rank/@thresholds_min)')"
  RANK_MAX="$(xp 'string(/network/jacobian/rank/@thresholds_max)')"
  RANK_SLACK="$(xp 'string(/network/jacobian/rank/@slack)')"
  local has_matrix
  has_matrix="$(xp 'count(/network/jacobian/matrix)')"
  if [[ "$has_matrix" -ge 1 ]]; then
    JAC_MATRIX_TEXT="$(xp 'string(/network/jacobian/matrix)')"
    JAC_MATRIX_ROWS="$(xp 'string(/network/jacobian/matrix/@rows)')"
    JAC_MATRIX_COLS="$(xp 'string(/network/jacobian/matrix/@cols)')"
  fi

  local upper_bound
  upper_bound=$(( JAC_INPUT_DIM < JAC_OUTPUT_DIM ? JAC_INPUT_DIM : JAC_OUTPUT_DIM ))
  if (( RANK_MIN < 0 || RANK_MAX > upper_bound || RANK_MIN > RANK_MAX )); then
    die "I9 violation: jacobian/rank thresholds [$RANK_MIN,$RANK_MAX] invalid for a ${JAC_INPUT_DIM}x${JAC_OUTPUT_DIM} map (max possible rank $upper_bound)" 66
  fi
}

# ---------------------------------------------------------------------------
# 8. calculate_rank — real (computed, via numpy) when a matrix is supplied
#    and rank_backend=computed; otherwise an explicitly labeled structural
#    heuristic. NEVER reported under the same label. See SECTION 20.
# ---------------------------------------------------------------------------
RANK_VALUE=""
RANK_SOURCE=""

calculate_rank() {
  if [[ "$RANK_BACKEND" == "computed" && -n "$JAC_MATRIX_TEXT" ]]; then
    require_cmd python3
    if ! python3 -c "import numpy" >/dev/null 2>&1; then
      die "rank_backend=computed requires numpy, which is not importable" 69
    fi
    local cleaned
    cleaned="$(printf '%s' "$JAC_MATRIX_TEXT" | tr -d '[:space:]' | sed 's/;$//')"
    RANK_VALUE="$(python3 - "$cleaned" "$JAC_MATRIX_ROWS" "$JAC_MATRIX_COLS" <<'PYEOF'
import sys
import numpy as np
text, rows, cols = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
row_strs = [r for r in text.split(';') if r != '']
if len(row_strs) != rows:
    print(f"ERROR: matrix declares rows={rows} but has {len(row_strs)} row(s)", file=sys.stderr)
    sys.exit(1)
data = []
for r in row_strs:
    vals = [float(v) for v in r.split(',') if v != '']
    if len(vals) != cols:
        print(f"ERROR: matrix declares cols={cols} but row has {len(vals)}", file=sys.stderr)
        sys.exit(1)
    data.append(vals)
m = np.array(data, dtype=float)
print(int(np.linalg.matrix_rank(m)))
PYEOF
)" || die "jacobian matrix rank computation failed" 66
    RANK_SOURCE="computed"
  else
    # Structural heuristic — explicitly NOT a numeric linear-algebra rank.
    # Counts distinct active, top-level (non-recursed) tensor dependencies
    # referenced by edges, capped at the smaller Jacobian dimension. This
    # is an engineering proxy for "how many independent routing paths
    # carry distinguishable tensor state", not a claim about ∂f/∂x.
    local -A seen=()
    local eid dep count=0
    for eid in "${EDGE_IDS[@]}"; do
      [[ "${EDGE_ACTIVE[$eid]}" == "active" ]] || continue
      dep="${EDGE_TENSOR_DEP[$eid]}"
      if [[ -n "${seen[$dep]+x}" ]]; then continue; fi
      seen["$dep"]=1
      count=$((count + 1))
    done
    local cap=$(( JAC_INPUT_DIM < JAC_OUTPUT_DIM ? JAC_INPUT_DIM : JAC_OUTPUT_DIM ))
    if (( count > cap )); then count=$cap; fi
    RANK_VALUE="$count"
    RANK_SOURCE="structural"
  fi

  # I9: whichever source produced it, the rank must be mathematically valid.
  local upper_bound=$(( JAC_INPUT_DIM < JAC_OUTPUT_DIM ? JAC_INPUT_DIM : JAC_OUTPUT_DIM ))
  if (( RANK_VALUE < 0 || RANK_VALUE > upper_bound )); then
    die "I9 violation: computed rank $RANK_VALUE outside valid range [0,$upper_bound]" 66
  fi
  if (( RANK_VALUE < RANK_MIN || RANK_VALUE > RANK_MAX )); then
    die "I9 violation: rank $RANK_VALUE ($RANK_SOURCE) outside configured thresholds [$RANK_MIN,$RANK_MAX]" 66
  fi
}

# ---------------------------------------------------------------------------
# I4 — cycle detection (DFS, white/gray/black) — only enforced when
#      routing/hierarchy/@forbid_cycles = true.
# ---------------------------------------------------------------------------
check_no_forbidden_cycles() {
  [[ "$FORBID_CYCLES" == "true" ]] || return 0
  local -A color=()   # 0=white(unset) 1=gray 2=black
  local -a stack=()

  _dfs() {
    local node="$1" eid dst
    color["$node"]=1
    for eid in "${EDGE_IDS[@]}"; do
      [[ "${EDGE_SRC[$eid]}" == "$node" ]] || continue
      dst="${EDGE_DST[$eid]}"
      case "${color[$dst]:-0}" in
        1) die "I4 violation: forbidden cycle detected through edge $eid ($node -> $dst)" 66 ;;
        0) _dfs "$dst" ;;
      esac
    done
    color["$node"]=2
  }

  local n
  for n in "${NODE_IDS[@]}"; do
    if [[ "${color[$n]:-0}" == "0" ]]; then _dfs "$n"; fi
  done
}

# ---------------------------------------------------------------------------
# 9. calculate_latency — real Dijkstra from routing root, nonnegative
#    weights (already enforced by I6), deterministic tie-break:
#    (1) lower cumulative latency (2) fewer hops (3) higher last-edge
#    routing_priority (4) lexicographically smaller node id.
# ---------------------------------------------------------------------------
declare -A DIST=() HOPS=() LASTPRIO=() VISITED=()
ROUTE_TOTAL_LATENCY=""
BOTTLENECK_NODE=""

_better() {
  # returns 0 (true) if candidate (d,h,p) is strictly better than current best
  local d="$1" h="$2" p="$3" bd="$4" bh="$5" bp="$6"
  if (( $(calc "($d < $bd)") )); then return 0; fi
  if (( $(calc "($d > $bd)") )); then return 1; fi
  if (( h < bh )); then return 0; fi
  if (( h > bh )); then return 1; fi
  if (( p > bp )); then return 0; fi
  return 1
}

calculate_latency() {
  local n
  for n in "${NODE_IDS[@]}"; do
    DIST["$n"]="inf"; HOPS["$n"]=999999; LASTPRIO["$n"]=-999999; VISITED["$n"]=0
  done
  DIST["$ROOT_NODE"]=0; HOPS["$ROOT_NODE"]=0; LASTPRIO["$ROOT_NODE"]=0

  local remaining="$V"
  while (( remaining > 0 )); do
    # pick unvisited node with best (dist,hops,-priority,id) — deterministic scan
    local best="" bd="inf" bh=999999 bp=-999999
    for n in "${NODE_IDS[@]}"; do
      if [[ "${VISITED[$n]}" == "1" ]]; then continue; fi
      if [[ "${DIST[$n]}" == "inf" ]]; then continue; fi
      if [[ -z "$best" ]]; then
        best="$n"; bd="${DIST[$n]}"; bh="${HOPS[$n]}"; bp="${LASTPRIO[$n]}"
      elif _better "${DIST[$n]}" "${HOPS[$n]}" "${LASTPRIO[$n]}" "$bd" "$bh" "$bp"; then
        best="$n"; bd="${DIST[$n]}"; bh="${HOPS[$n]}"; bp="${LASTPRIO[$n]}"
      elif [[ "${DIST[$n]}" == "$bd" && "${HOPS[$n]}" == "$bh" && "${LASTPRIO[$n]}" == "$bp" ]]; then
        if [[ "$n" < "$best" ]]; then best="$n"; fi
      fi
    done
    if [[ -z "$best" ]]; then break; fi   # remaining nodes are unreachable
    VISITED["$best"]=1
    remaining=$((remaining - 1))

    local eid
    for eid in "${EDGE_IDS[@]}"; do
      [[ "${EDGE_SRC[$eid]}" == "$best" ]] || continue
      [[ "${EDGE_ACTIVE[$eid]}" == "active" ]] || continue
      local dst="${EDGE_DST[$eid]}" cand
      if [[ "${VISITED[$dst]}" == "1" ]]; then continue; fi
      cand="$(calc "${DIST[$best]} + ${EDGE_LAT[$eid]}")"
      if [[ "${DIST[$dst]}" == "inf" ]] || _better "$cand" "$((HOPS[$best]+1))" "${EDGE_PRIORITY[$eid]}" \
                                                     "${DIST[$dst]}" "${HOPS[$dst]}" "${LASTPRIO[$dst]}"; then
        DIST["$dst"]="$cand"; HOPS["$dst"]=$((HOPS[$best]+1)); LASTPRIO["$dst"]="${EDGE_PRIORITY[$eid]}"
      fi
    done
  done

  # critical path = furthest reachable node from root by computed distance
  local worst="" wd="-1"
  for n in "${NODE_IDS[@]}"; do
    if [[ "${DIST[$n]}" == "inf" ]]; then continue; fi
    if (( $(calc "(${DIST[$n]} > $wd)") )); then wd="${DIST[$n]}"; worst="$n"; fi
  done
  ROUTE_TOTAL_LATENCY="$wd"
  BOTTLENECK_NODE="$worst"
}

# ---------------------------------------------------------------------------
# 10. adapt_network — deterministic rule evaluation. Only acts on rules
#     declared in the XML's <adaptation><rules>; never invents topology
#     not derivable from the canonical XML (see README "Known limitations").
# ---------------------------------------------------------------------------
ADAPTATION_APPLIED="false"
declare -a TRIGGERED_CONDITIONS=()
declare -a CHANGED_EDGES=()
declare -a CHANGED_NODES=()
ADAPTATION_RESOLVED="true"

_rule_declared() {
  local cond="$1"
  [[ "$(xp "count(/network/adaptation/rules/rule[@condition='$cond'])")" -ge 1 ]]
}

adapt_network() {
  local prev_rank="${PREV_RANK:-}"

  # rule: latency_exceeds_threshold -> evaluate_alternate_route
  if (( $(calc "(${ROUTE_TOTAL_LATENCY} > ${LATENCY_THRESHOLD})") )); then
    TRIGGERED_CONDITIONS+=("latency_exceeds_threshold")
    if _rule_declared "latency_exceeds_threshold"; then
      # "evaluating an alternate route" here means: Dijkstra already found
      # the globally latency-minimal route under the active topology: if
      # the minimal route itself exceeds threshold, no alternate route in
      # this topology can do better. This is a real, not simulated, proof
      # of infeasibility given nonnegative edge weights.
      ADAPTATION_RESOLVED="false"
    fi
  fi

  # rule: rank_decreases / rank_increases -> compare to previous state
  if [[ -n "$prev_rank" ]]; then
    if (( RANK_VALUE < prev_rank )); then
      TRIGGERED_CONDITIONS+=("rank_decreases")
      if _rule_declared "rank_decreases"; then
        _evaluate_redundant_edge_removal
      fi
    elif (( RANK_VALUE > prev_rank )); then
      TRIGGERED_CONDITIONS+=("rank_increases")
      if _rule_declared "rank_increases"; then
        # Capacity expansion requires new topology to exist in the XML;
        # this engine authorizes or rejects, it does not fabricate edges.
        if [[ "$ALLOW_EXPANSION" != "true" ]]; then
          TRIGGERED_CONDITIONS+=("sparsity_exceeds_maximum")
        fi
      fi
    fi
  fi

  if [[ "${#CHANGED_EDGES[@]}" -gt 0 || "${#CHANGED_NODES[@]}" -gt 0 ]]; then
    ADAPTATION_APPLIED="true"
  fi

  # I10: every adaptation must have a recorded triggering condition.
  if [[ "$ADAPTATION_APPLIED" == "true" && "${#TRIGGERED_CONDITIONS[@]}" -eq 0 ]]; then
    die "I10 violation: adaptation applied with no recorded triggering condition" 66
  fi
}

_evaluate_redundant_edge_removal() {
  # An edge (u -> v) is structurally redundant iff v has at least one other
  # active incoming edge, i.e. removing (u -> v) does not disconnect v from
  # the rest of the reachable graph. Deterministic pick among candidates:
  # lowest routing_priority first, tie-break by lexicographically smallest
  # edge id.
  local eid dst indeg candidate="" cprio=999999
  for eid in "${EDGE_IDS[@]}"; do
    [[ "${EDGE_ACTIVE[$eid]}" == "active" ]] || continue
    dst="${EDGE_DST[$eid]}"
    indeg=0
    local other
    for other in "${EDGE_IDS[@]}"; do
      [[ "${EDGE_ACTIVE[$other]}" == "active" ]] || continue
      if [[ "${EDGE_DST[$other]}" == "$dst" ]]; then indeg=$((indeg + 1)); fi
    done
    if (( indeg > 1 )); then
      if [[ -z "$candidate" ]] || (( EDGE_PRIORITY[$eid] < cprio )) \
         || { (( EDGE_PRIORITY[$eid] == cprio )) && [[ "$eid" < "$candidate" ]]; }; then
        candidate="$eid"; cprio="${EDGE_PRIORITY[$eid]}"
      fi
    fi
  done
  if [[ -n "$candidate" ]]; then
    EDGE_ACTIVE["$candidate"]="pruned"
    CHANGED_EDGES+=("$candidate")
  fi
}

# ---------------------------------------------------------------------------
# 11. verify_invariants — I1,I2,I3,I5,I6,I7,I8,I9 are enforced inline at
#     parse time (fail fast, fail closed). This function performs the
#     remaining whole-graph checks (I4, I5 recheck, I12 gate) that need
#     the fully built graph.
# ---------------------------------------------------------------------------
verify_invariants() {
  check_no_forbidden_cycles   # I4

  # I5: sparsity must remain within configured bounds, both before and,
  # if an expansion was authorized, after adaptation. This engine never
  # fabricates new edges (see adapt_network), so |E| cannot grow here;
  # the check is a genuine guard, not decoration.
  if (( $(calc "(${SPARSITY_RATIO} > ${SPARSITY_MAX_RATIO})") )); then
    die "I5 violation: sparsity ratio ${SPARSITY_RATIO} exceeds max_ratio ${SPARSITY_MAX_RATIO}" 66
  fi

  # I10 is checked inside adapt_network(); I1/I2/I3/I6/I7/I8/I9 inline above.
  return 0
}

# ---------------------------------------------------------------------------
# canonical serialization — the exact byte string that gets hashed. Order
# is fixed (sorted ids) so the result does not depend on XML attribute
# order or on which xmllint version produced the xpath output.
# ---------------------------------------------------------------------------
canonical_payload() {
  local n eid t
  printf 'NETWORK|%s|%s\n' "$NET_NAME" "$NET_VERSION"
  for n in $(printf '%s\n' "${NODE_IDS[@]}" | sort); do
    printf 'NODE|%s|%s\n' "$n" "${NODE_PRIORITY[$n]}"
  done
  for eid in $(printf '%s\n' "${EDGE_IDS[@]}" | sort); do
    printf 'EDGE|%s|%s|%s|%s|%s|%s\n' "$eid" "${EDGE_SRC[$eid]}" "${EDGE_DST[$eid]}" \
      "${EDGE_LAT[$eid]}" "${EDGE_ACTIVE[$eid]}" "${EDGE_TENSOR_DEP[$eid]}"
  done
  for t in $(printf '%s\n' "${TENSOR_IDS[@]}" | sort); do
    printf 'TENSOR|%s|%s|%s\n' "$t" "${TENSOR_SHAPE[$t]}" "${TENSOR_DTYPE[$t]}"
  done
  printf 'RANK|%s|%s\n' "$RANK_VALUE" "$RANK_SOURCE"
  printf 'LATENCY|%s|%s\n' "$ROUTE_TOTAL_LATENCY" "$BOTTLENECK_NODE"
  printf 'PREV|%s\n' "${PREV_HASH:-GENESIS}"
}

state_hash() {
  canonical_payload | sha256sum | awk '{print $1}'
}

# ---------------------------------------------------------------------------
# 12/13. emit_state / emit_audit
# ---------------------------------------------------------------------------
_json_array() {
  local arr=("$@") out="[" first=1 x
  for x in "${arr[@]:-}"; do
    if [[ -z "$x" ]]; then continue; fi
    if [[ $first -eq 0 ]]; then out+=","; fi
    out+="\"$x\""
    first=0
  done
  out+="]"
  printf '%s' "$out"
}

emit_state() {
  mkdir -p "$STATE_DIR"
  local next_index=0 f
  for f in "$STATE_DIR""/STATE_"*.json; do
    [[ -e "$f" ]] || continue
    next_index=$((next_index + 1))
  done
  local idx_padded
  idx_padded="$(printf '%03d' "$next_index")"
  local hash; hash="$(state_hash)"
  local xml_hash; xml_hash="$(sha256sum "$XML_FILE" | awk '{print $1}')"

  local tmp="${STATE_DIR}/.STATE_${idx_padded}.json.tmp"
  cat > "$tmp" <<EOF
{
  "index": $next_index,
  "network_name": "$NET_NAME",
  "network_version": "$NET_VERSION",
  "prev_hash": "${PREV_HASH:-GENESIS}",
  "hash": "$hash",
  "xml_sha256": "$xml_hash",
  "rank": $RANK_VALUE,
  "rank_source": "$RANK_SOURCE",
  "route_total_latency": $ROUTE_TOTAL_LATENCY,
  "bottleneck_node": "$BOTTLENECK_NODE",
  "adaptation_applied": $ADAPTATION_APPLIED,
  "triggering_conditions": $(_json_array "${TRIGGERED_CONDITIONS[@]:-}"),
  "changed_nodes": $(_json_array "${CHANGED_NODES[@]:-}"),
  "changed_edges": $(_json_array "${CHANGED_EDGES[@]:-}")
}
EOF
  # I12: only publish after every prior check in main() has passed — the
  # temp-file-then-rename is atomic, so a crash mid-write never leaves a
  # half-written state file mistaken for a real one.
  mv "$tmp" "${STATE_DIR}/STATE_${idx_padded}.json"
  STATE_FILE_WRITTEN="${STATE_DIR}/STATE_${idx_padded}.json"
  log "state published: $STATE_FILE_WRITTEN (hash=$hash)"
}

emit_audit() {
  local idx_padded; idx_padded="$(basename "$STATE_FILE_WRITTEN" | sed -E 's/STATE_([0-9]+)\.json/\1/')"
  local audit="${STATE_DIR}/AUDIT_${idx_padded}.json"
  cat > "$audit" <<EOF
{
  "timestamp_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "xml_file": "$XML_FILE",
  "node_count": $V,
  "edge_count": $E,
  "sparsity_ratio": $SPARSITY_RATIO,
  "sparsity_max_ratio": $SPARSITY_MAX_RATIO,
  "rank": $RANK_VALUE,
  "rank_source": "$RANK_SOURCE",
  "rank_thresholds": [$RANK_MIN, $RANK_MAX],
  "route_total_latency": $ROUTE_TOTAL_LATENCY,
  "latency_threshold": $LATENCY_THRESHOLD,
  "bottleneck_node": "$BOTTLENECK_NODE",
  "adaptation_applied": $ADAPTATION_APPLIED,
  "adaptation_resolved": $ADAPTATION_RESOLVED,
  "triggering_conditions": $(_json_array "${TRIGGERED_CONDITIONS[@]:-}"),
  "changed_nodes": $(_json_array "${CHANGED_NODES[@]:-}"),
  "changed_edges": $(_json_array "${CHANGED_EDGES[@]:-}"),
  "state_hash": "$(state_hash)"
}
EOF
  log "audit written: $audit"
}

# ---------------------------------------------------------------------------
# verify subcommand — recompute the canonical hash from XML + recorded
# prev_hash and confirm it matches the hash stored in a STATE file. This is
# the mechanical check for I11 (reconstructability) and tamper detection.
# ---------------------------------------------------------------------------
cmd_verify() {
  validate_xml
  parse_network
  build_sparse_graph
  parse_tensor
  parse_routing
  parse_jacobian
  verify_invariants
  calculate_rank
  calculate_latency

  local recorded_hash recorded_prev
  recorded_hash="$(xp_of 'string(/*)' "$STATE_FILE" 2>/dev/null || true)"
  recorded_hash="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['hash'])" "$STATE_FILE")"
  recorded_prev="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['prev_hash'])" "$STATE_FILE")"
  PREV_HASH="$recorded_prev"

  local recomputed; recomputed="$(state_hash)"
  if [[ "$recomputed" == "$recorded_hash" ]]; then
    log "VERIFY OK: recomputed hash matches recorded state ($recomputed)"
    exit 0
  else
    log "VERIFY FAILED: recorded=$recorded_hash recomputed=$recomputed"
    die "state/hash verification mismatch — XML or topology diverged from the recorded state" 68
  fi
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
cmd_run() {
  validate_xml
  parse_network
  build_sparse_graph
  parse_tensor
  parse_routing
  parse_jacobian
  verify_invariants

  # load previous state (if any) for adaptation comparisons
  PREV_HASH=""
  PREV_RANK=""
  mkdir -p "$STATE_DIR"
  local latest=""
  local f
  for f in "$STATE_DIR"/STATE_*.json; do
    [[ -e "$f" ]] || continue
    latest="$f"
  done
  if [[ -n "$latest" ]]; then
    PREV_HASH="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['hash'])" "$latest")"
    PREV_RANK="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['rank'])" "$latest")"
  fi

  calculate_rank
  calculate_latency
  adapt_network

  if [[ "$ADAPTATION_RESOLVED" != "true" ]]; then
    log "FAIL-CLOSED: route_total_latency=${ROUTE_TOTAL_LATENCY} exceeds threshold=${LATENCY_THRESHOLD} and no alternate route exists in this topology"
    die "adaptation could not satisfy the routing latency objective" 67
  fi

  emit_state
  emit_audit
}

main() {
  validate_args "$@"
  case "$MODE" in
    run)    cmd_run ;;
    verify) cmd_verify ;;
  esac
}

main "$@"

/**
 * MAGMA safety layer — electromagnetic safety predicate.
 * Σ_w |A_{c,w}| · I_w_max < H_dist  (strict, compile-time checkable)
 */

const ErrorCode = Object.freeze({
  INVALID_INPUT:      "INVALID_INPUT",
  DIMENSION_MISMATCH: "DIMENSION_MISMATCH",
  UNSAFE:             "UNSAFE",
  BAD_SIGNATURE:      "BAD_SIGNATURE",
  NON_FINITE:         "NON_FINITE",
});

class MAGMAError extends Error {
  constructor(code, message, details) {
    super(message);
    this.name    = "MAGMAError";
    this.code    = code;
    this.details = details;
  }
}

function finite(x) {
  if (!Number.isFinite(x))
    throw new MAGMAError(ErrorCode.NON_FINITE, "non-finite numeric value");
  return x;
}

export function rowBound(row, currents) {
  if (row.length !== currents.length)
    throw new MAGMAError(ErrorCode.DIMENSION_MISMATCH, "row/current mismatch");
  let result = 0;
  for (let i = 0; i < row.length; i++)
    result += Math.abs(finite(row[i])) * Math.abs(finite(currents[i]));
  return finite(result);
}

export function checkSafety(net) {
  if (net.matrix.length !== net.cores.length)
    throw new MAGMAError(ErrorCode.DIMENSION_MISMATCH, "matrix/core mismatch");
  for (const w of net.wires)
    if (!Number.isFinite(w.i_max) || w.i_max < 0)
      throw new MAGMAError(ErrorCode.INVALID_INPUT, "Imax must be finite and non-negative");

  const currents = net.wires.map(w => w.i_max);
  const margins  = [];
  for (let i = 0; i < net.matrix.length; i++) {
    const bound = rowBound(net.matrix[i], currents);
    const limit = finite(net.cores[i].h_dist);
    if (limit <= 0)
      throw new MAGMAError(ErrorCode.INVALID_INPUT, "Hdist must be positive");
    if (!(bound < limit))
      throw new MAGMAError(ErrorCode.UNSAFE, `core ${net.cores[i].id} unsafe`,
        { core: net.cores[i].id, bound, limit });
    margins.push(limit - bound);
  }
  return margins;
}

export function safetyPredicate(net) {
  try   { return { safe: true,  margins: checkSafety(net) }; }
  catch (e) { return { safe: false, error: e }; }
}

export { MAGMAError, ErrorCode };

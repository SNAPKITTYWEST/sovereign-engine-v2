/**
 * Recursive orphan-node graph — MAGMA computation forest.
 * No scheduler. No automation. No regex. No network.
 * Functor is isolated from RBG layer.
 */

export class OrphanNode {
  constructor(value, functor = null) {
    this.value    = value;
    this.functor  = functor;
    this.children = [];
  }

  append(child) {
    if (!(child instanceof OrphanNode))
      throw new TypeError("child must be an OrphanNode");
    this.children.push(child);
    return child;
  }

  evaluate(context) {
    return this.functor !== null
      ? this.functor(this.value, context)
      : this.value;
  }

  evaluateRecursive(context) {
    return {
      value:    this.evaluate(context),
      children: this.children.map(c => c.evaluateRecursive(context)),
    };
  }
}

export const createOrphan  = (v, f = null) => new OrphanNode(v, f);
export const appendOrphan  = (p, v, f = null) => p.append(new OrphanNode(v, f));

export function walkOrphans(root, visitor) {
  if (!(root instanceof OrphanNode)) throw new TypeError("root must be OrphanNode");
  visitor(root);
  for (const c of root.children) walkOrphans(c, visitor);
}

export function reduceOrphans(root, reducer, initial) {
  let acc = initial;
  walkOrphans(root, node => { acc = reducer(acc, node); });
  return acc;
}

export function orphanDepth(root) {
  if (root.children.length === 0) return 1;
  return 1 + Math.max(...root.children.map(orphanDepth));
}

export const orphanSize = root => reduceOrphans(root, n => n + 1, 0);

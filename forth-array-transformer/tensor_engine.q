/ ═══════════════════════════════════════════════════════════════════════════
/ PART IV — q/kdb+ TENSOR ENGINE (namespace .tensor)
/
/ A complete, self-contained tensor algebra built entirely from q's
/ iterators, adverbs, and self-reference. No C extensions. No FFI.
/ Every kernel below is a lambda composed from primitives.
/
/ The engine is organised as nine sections:
/ §1 Primitives — constructors, shapes, ranks
/ §2 Iterators — / \ ' /: \: each, converge, scan
/ §3 Structural recursion — .z.s deep apply / map / zip
/ §4 Reductions — sum, product, min, max, mean, var
/ §5 Linear algebra — dot, matmul, transpose, outer
/ §6 Activations — relu, sigmoid, tanh, softmax, gelu
/ §7 Bridge → AVX-512 — serialise / hash / handoff
/ §8 Bridge → ColorForth — colour-tagged token stream
/ §9 Bridge → GA144 mesh — nodes as dicts, ports as queues
/ §10 Root of Trust — hash chain, verify, release
/ ═══════════════════════════════════════════════════════════════════════════

\d .tensor


/ ───────────────────────────────────────────────────────────────────────────
/ §1 PRIMITIVES — constructors, shape, rank, element access
/ ───────────────────────────────────────────────────────────────────────────

/ 1.1 The user's original triplet, preserved verbatim.
/ `raze/` is a converge loop: raze strips one level of nesting each
/ iteration, and `/` (converge) repeats until output = input.
flatten: {raze/ x}

/ 1.2 `deepApply` recurses on structure, not on count. `.z.s` is
/ the lambda's own name; when the argument is a list (type >= 0h) we
/ recurse into each element, otherwise we hand the atom to `f`.
deepApply: {[f; x] $[type[x]>=0h; .z.s[f] each x; f x]}

/ 1.3 Free-handed dot product: +/ (fold-add) over a *\: b
/ (each-left broadcast). This is the tensor MAC in its purest form.
dotProd: {[a;b] +/ a *\: b}

/ 1.4 Example rank-4 tensor.
p4_tensor: 2 2 2 2 # til 16

/ 1.5 Deep sum of an arbitrary-rank tensor.
deepSum: {+/ flatten x}


/ 1.6 Shape: the length of each successive level, stopping when we
/ hit atoms. Implemented by recursing on the head element and
/ prepending the outer count.
shape: {[x]
    $[type[x] < 0h; enlist 0;
      0 = count x; enlist 0;
      (count x), .z.s first x]
    }

/ 1.7 Rank = number of shape entries minus the terminal atom marker.
rank: {count[shape x] - 1}

/ 1.8 Size = total number of atoms.
size: {count flatten x}

/ 1.9 A quick reshape that fills row-major from a flat vector.
reshape: {[dims; flat]
    rec: {[dims; v]
        $[1 = count dims;
            dims[0] # v;
            [d: dims[0];
             n: (*/) dims _ 1;
             chunks: (-d) cut v;
             chunks: $[d = count chunks; chunks; (d, n) # v];
             .z.s[dims _ 1] each chunks]]
        } ;
    rec[dims; flat]
    }

/ 1.10 Element at a path (list of indices, 0-based).
at: {[x; path] .[x; path]}

/ 1.11 Update element at a path.
put: {[x; path; v] .[x; enlist path; :; v]}


/ ───────────────────────────────────────────────────────────────────────────
/ §2 ITERATORS — the whole engine is built from these six adverbs
/ ───────────────────────────────────────────────────────────────────────────

iter_over: {[f; x] f/ x}
iter_scan: {[f; x] f\ x}
iter_each: {[f; x] f' x}
iter_er: {[f; x; y] x f/: y}
iter_el: {[f; x; y] x f\: y}
iter_eb: {[f; x; y] x f' y}

converge: {x/ y}
do: {[n; f; x] n f/ x}
whilst: {[test; f; x] test f/ x}
fold_axis0: {[f; x] $[type[x] >= 0h; f over x; x]}
scan_axis0: {[f; x] $[type[x] >= 0h; f scan x; x]}
mapidx: {[f; x] {[f; i; v] f[i; v]} [f]'[til count x; x]}
zip: {[f; a; b] f'[a; b]}
zip3: {[f; a; b; c] f'[a; b; c]}
islist: {type[x] >= 0h}


/ ───────────────────────────────────────────────────────────────────────────
/ §3 STRUCTURAL RECURSION — .z.s and friends
/ ───────────────────────────────────────────────────────────────────────────

deepMap: {[f; x] $[islist x; .z.s[f] each x; f x]}

deepZip: {[f; a; b]
    $[islist a;
        $[islist b;
            .z.s[f]'[a; b];
            .z.s[f]'[a; (count a) # b]];
        $[islist b;
            .z.s[f]'[(count b) # a; b];
            f[a; b]]]
    }

deepFilter: {[pred; x] $[islist x; raze .z.s[pred] each x; $[pred x; enlist x; ()]]}

deepReduce: {[f; x]
    $[islist x;
        $[0 = count x; x;
            $[islist first x; .z.s[f] each x; f/ x]];
        x]
    }

equalShape: {[a; b] (shape a) ~ shape b}
equalDeep: {[a; b] (equalShape[a; b]) & (flatten a) ~ flatten b}

broadcast: {[x; target]
    xs: shape x;
    $[xs ~ target; x;
      1 = count target;
          (target[0]; x);
      count[target] > count xs;
          (target[0]; .z.s[x; target _ 1]);
      xs[0] = target[0];
          .z.s[; target _ 1] each x;
      'broadcast_shape_mismatch]
    }

slice0: {[x; i; j] (j - i) # (i) _ x}
transpose2: {flip x}
transpose3: {[x] flip each flip each x}
sumAxis: {[x; i] $[i = 0; +/ x; .z.s[; i-1] each x]}


/ ───────────────────────────────────────────────────────────────────────────
/ §4 REDUCTIONS
/ ───────────────────────────────────────────────────────────────────────────

sum: {+/ flatten x}
product: {*/ flatten x}
minimum: {&/ flatten x}
maximum: {|/ flatten x}
mean: {sum[x] % size x}
varp: {m: mean x; sum {(y - m) xexp 2}'[flatten x] % size x}
vars: {m: mean x; sum {(y - m) xexp 2}'[flatten x] % (size x) - 1}
stdevp: {sqrt varp x}
stdevs: {sqrt vars x}
cumsum: {+\ flatten x}
cumprod: {*\ flatten x}
argmin: {flatten[x] ? &/ flatten x}
argmax: {flatten[x] ? |/ flatten x}
l1norm: {sum abs flatten x}
l2norm: {sqrt sum {(y) xexp 2}'[flatten x]}
linf: {|/ abs flatten x}
l2normalise: {[x] x % l2norm x}
standardise: {[x] (x - mean x) % stdevp x}


/ ───────────────────────────────────────────────────────────────────────────
/ §5 LINEAR ALGEBRA — free-handed, no mmu
/ ───────────────────────────────────────────────────────────────────────────

inner: {[a; b] +/ a * b}
outer: {[a; b] a */: b}
mv: {[A; x] A +/:\: x}
vm: {[x; A] A +/:\: x}
mm2row: {[col; row] +/ row * col}
mm2: {[row; B] B mm2row\: row}
mm: {[A; B] A mm2\: B}
dotProd: {[a; b] +/ a *\: b}
bmm: {[A; B] mm'[A; B]}
trace: {[A] sum {[A; i] A[i; i]}'[A; til count A]}
eye: {[n] {x = y} '[;] / [til n; til n]}
diag: {[A] {x[y;y]}'[A; til count A]}
outerOp: {[f; a; b] a f/: b}


/ ───────────────────────────────────────────────────────────────────────────
/ §6 ACTIVATIONS — element-wise, built from primitives
/ ───────────────────────────────────────────────────────────────────────────

relu: {[x] deepMap[{0f | x}; x]}
leaky: {[a; x] deepMap[{?[y < 0; a * y; y]}; x]}
sigmoid: {[x] deepMap[{1 % 1 + exp -x}; x]}
tanh: {[x] deepMap[{e: exp 2 * x; (e - 1) % e + 1}; x]}

sqrt2pi: sqrt 2 % sqrt acos -1
gelu: {[x] deepMap[{0.5 * x * 1 + tanh sqrt2pi * x + 0.044715 * x xexp 3}; x]}

softmaxFlat: {[v]
    m: max v;
    e: exp v - m;
    e % sum e
    }
softmax: {[x] reshape[shape x; softmaxFlat flatten x]}
onehot: {[n; i] (n # 0f) , (i # 0f), 1f, (n - i - 1) # 0f}


/ ───────────────────────────────────────────────────────────────────────────
/ §7 BRIDGE → PART I (AVX-512) — serialise / hash / handoff
/ ───────────────────────────────────────────────────────────────────────────

.serialise: {[x] -8! x}
.deserialise: {[b] -9! b}

.hash: {[b]
    h: 0xcbf29ce484222325;
    h: {[h; c] (h xor c) * 0x100000001b3} / [h] over b;
    h
    }

.sendAVX: {[op; x]
    blob: .serialise (op; x);
    h: .hash blob;
    (`.avx.pending) upsert (h; blob);
    h
    }

.recvAVX: {[h]
    $[h in key `.avx.results;
        -9! .avx.results h;
        'avx_result_not_ready]
    }

.avx_ops: `vadd`vsub`vmul`vscale`vdot`relu`sigmoid`tanh`softmax`gelu`layernorm

.avxCall: {[op; x; timeoutMs]
    h: .sendAVX[op; x];
    deadline: .z.p + timeoutMs * 0D00:00:00.001;
    while[.z.p < deadline;
        $[h in key `.avx.results; : .recvAVX h; system "sleep 0.001"]];
    'avx_timeout
    }


/ ───────────────────────────────────────────────────────────────────────────
/ §8 BRIDGE → PART II (ColorForth) — colour-tagged token stream
/ ───────────────────────────────────────────────────────────────────────────

.cf.colours: `white`red`green`yellow`blue
.cf.token: {[colour; text] (colour; text)}

.cf.exec: {[tok]
    $[tok ~ "dup"; .cf.stack,: last .cf.stack;
      tok ~ "drop"; .cf.stack: -1 _ .cf.stack;
      tok ~ "+"; .cf.stack: (-2 # .cf.stack) , (sum -2 # .cf.stack);
      tok ~ "*"; .cf.stack: (-2 # .cf.stack) , (*/ -2 # .cf.stack);
      tok ~ "bye"; 'bye_from_colorforth;
      (0N! tok; ::)]
    }

.cf.emit: {[tensor]
    block: ();
    block,: .cf.token[`red; "tensor"];
    {[block; v] block,: .cf.token[`green; string v]} [block] / over flatten tensor;
    block,: .cf.token[`yellow; "bye"];
    block
    }

.sendCF: {[tensor]
    block: .cf.emit tensor;
    (`.cf.pending) upsert (ticket: .hash -8! block; block);
    ticket
    }


/ ───────────────────────────────────────────────────────────────────────────
/ §9 BRIDGE → PART III (GA144 mesh) — nodes as dicts, ports as queues
/ ───────────────────────────────────────────────────────────────────────────

.ga.NODE_COUNT: 144
.ga.MESH_W: 18
.ga.MESH_H: 8
.ga.PORTS: `up`right`down`left

.ga.mkNode: {[idx]
    `idx`p`a`t`s`r`state`ports`rom`ram`cycles`instrs!
    (idx; 0; 0; 0; 0; 0; `reset;
     (`.up`right`down`left)!((); (); (); ());
     (); (); 0; 0)
    }

.ga.mkMesh: {[]
    (!) . (til .ga.NODE_COUNT; {.ga.mkNode x} each til .ga.NODE_COUNT)
    }

.ga.xy: {[idx] (idx mod .ga.MESH_W; idx div .ga.MESH_W)}
.ga.idx: {[x; y] y * .ga.MESH_W + x}
.ga.inBounds:{[x; y] (x >= 0) & (x < .ga.MESH_W) & (y >= 0) & (y < .ga.MESH_H)}

.ga.neighbour: {[idx; dir]
    xy: .ga.xy idx;
    x: xy 0; y: xy 1;
    $[dir = `up; $[y > 0; .ga.idx[x; y - 1]; -1];
      dir = `right; $[x < .ga.MESH_W - 1; .ga.idx[x + 1; y]; -1];
      dir = `down; $[y < .ga.MESH_H - 1; .ga.idx[x; y + 1]; -1];
      dir = `left; $[x > 0; .ga.idx[x - 1; y]; -1];
      'bad_direction]
    }

.ga.route: {[src; dst]
    s: .ga.xy src; d: .ga.xy dst;
    h: $[s 0 < d 0; (d 0 - s 0) # `right;
         s 0 > d 0; (s 0 - d 0) # `left; ()];
    v: $[s 1 < d 1; (d 1 - s 1) # `down;
         s 1 > d 1; (s 1 - d 1) # `up; ()];
    h , v
    }

.ga.send: {[mesh; idx; dir; word]
    n: mesh idx;
    p: n[`ports];
    p[dir]: p[dir], word;
    n[`ports]: p;
    mesh[idx]: n;
    mesh
    }

.ga.recv: {[mesh; idx; dir]
    n: mesh idx;
    p: n[`ports];
    q: p dir;
    $[0 = count q; (mesh; 0N);
      [w: first q; p[dir]: 1 _ q; n[`ports]: p; mesh[idx]: n; (mesh; w)]]
    }

.ga.simStream: {[src; dst; buf]
    r: .ga.route[src; dst];
    (buf; r)
    }

.ga.loadROM: {[mesh; idx; rom]
    n: mesh idx;
    n[`rom]: rom;
    mesh[idx]: n;
    mesh
    }

.ga.tickMesh: {[mesh]
    {.ga.tick[x; y]}/[mesh; til .ga.NODE_COUNT]
    }


/ ───────────────────────────────────────────────────────────────────────────
/ §10 ROOT OF TRUST — hash chain, verify, release
/ ───────────────────────────────────────────────────────────────────────────

.rot.MAGIC: 0x47413434
.rot.HASH_A: 0x1F123BB5
.rot.HASH_B: 0x2C1B3C6D
.rot.MASK: 0x3FFFF

.rot.mix: {[h; w]
    x: .rot.MASK & h xor w;
    x: .rot.MASK & x * .rot.HASH_A;
    x: x xor x div 128;
    x: .rot.MASK & x * .rot.HASH_B;
    x: x xor x div 8192;
    .rot.MASK & x
    }

.rot.hash: {[init; words]
    h: init;
    {h:: .rot.mix[h; x]} each words;
    h
    }

.rot.measure: {[mesh; idx; chain]
    n: mesh idx;
    h1: .rot.hash[.rot.MAGIC; n[`rom]];
    h2: .rot.hash[h1; n[`ram]];
    newChain: .rot.mix[chain; h2];
    (newChain; h2)
    }

.rot.measureMesh: {[mesh]
    h: .rot.MAGIC;
    hashes: ();
    {[h; hashes; mesh; i]
        (h2; nodeHash): .rot.measure[mesh; i; h];
        h: h2;
        hashes,: nodeHash;
        (h; hashes)
        } [h; hashes; mesh] / over til .ga.NODE_COUNT
    }

.rot.verify: {[computed; expected] computed = expected}

.rot.release: {[mesh; idx; valid]
    $[valid;
        [n: mesh idx; n[`state]: `ready; mesh[idx]: n; mesh];
        mesh]
    }

.rot.boot: {[roms]
    mesh: .ga.mkMesh[];
    {[mesh; roms; i]
        .ga.loadROM[mesh; i; roms i]
        } [mesh; roms] / over til .ga.NODE_COUNT;
    (root; hashes): .rot.measureMesh mesh;
    valid: .rot.verify[root; .rot.KEY];
    mesh
    }


/ ───────────────────────────────────────────────────────────────────────────
/ §11 INTEGRATION — the whole pipeline in one expression
/ ───────────────────────────────────────────────────────────────────────────

show: {-1 @ x; ::}

.demo.pipeline: {[]
    t: p4_tensor;
    show "p4_tensor = ", t;
    show "shape = ", shape t;
    show "rank = ", rank t;
    show "size = ", size t;
    show "flatten = ", flatten t;
    show "deepSum = ", deepSum t;
    show "relu = ", relu t;
    show "sigmoid = ", sigmoid t;
    show "tanh = ", tanh t;
    show "softmax = ", softmax flatten t;
    A: (2 3) # 1 2 3 4 5 6f;
    B: (3 2) # 7 8 9 10 11 12f;
    show "A mm B = ", mm[A; B];
    show "transpose = ", transpose2 A;
    show "outer = ", outer[1 2 3f; 4 5f];
    h: .sendAVX[`relu; t];
    show "avx ticket = ", h;
    blk: .cf.emit t;
    show "cf block = ", blk;
    mesh: .ga.mkMesh[];
    (delivered; route): .ga.simStream[0; 3; flatten t];
    show "ga route = ", route;
    show "ga deliv = ", delivered;
    root: .rot.hash[.rot.MAGIC; flatten t];
    show "rot root = ", root;
    ::
    }

/ ═══════════════════════════════════════════════════════════════════════════
/ END OF PART IV
/
/ Recap of the trilogy:
/ Part I — AVX-512 NN kernels (C/asm, 16 sections)
/ Part II — ColorForth hosted env (asm, 23 sections)
/ Part III — GA144 / hardware Forth (asm, 10 sections)
/ Part IV — q/kdb+ tensor engine (q, 11 sections, this file)
/ ═══════════════════════════════════════════════════════════════════════════

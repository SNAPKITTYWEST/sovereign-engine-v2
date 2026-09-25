//! functoriality_of_tor
//!
//! Functoriality of Tor in its first argument. A homomorphism `f: M → M'`,
//! given on generators by a matrix `F_0: P_0 → P'_0` between presentations,
//! is lifted to a chain map `F_k: P_k → P'_k` (solving `d'_k F_k = F_{k-1} d_k`
//! over Z), tensored with a resolution `Q` of `N`, and pushed to homology:
//! `f_*: Tor_n(M, N) → Tor_n(M', N)`.
//!
//! Homology classes are expressed in explicit generators obtained from the
//! Smith decomposition of `d_{n+1}` in kernel coordinates, ordered torsion
//! first (ascending order) then free — the same order as `TorGroup`.

#![warn(missing_docs)]

use derived_homology::{resolution_data, tensor_resolutions, TensoredComplex};
pub use derived_homology::verify_tor_computation;
use tor_functor_definition::integer_matrix::{apply, is_zero, multiply, smith_decomposition, smith_form, solve};
pub use tor_functor_definition::{ProjectiveResolution, TorComputation, TorGroup, TorIndex};

/// A homomorphism between modules on fixed generators: entry `(i, j)` is the
/// coefficient of target generator `j` in the image of source generator `i`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModuleMap {
    /// Source rank
    pub source_rank: usize,
    /// Target rank
    pub target_rank: usize,
    /// Row-major entries, `matrix[i * target_rank + j]`
    pub matrix: Vec<i32>,
}

impl ModuleMap {
    /// The zero map.
    pub fn new(source_rank: usize, target_rank: usize) -> Self {
        Self {
            source_rank,
            target_rank,
            matrix: vec![0; source_rank * target_rank],
        }
    }

    /// Set entry `(i, j)`; out-of-range indices are ignored.
    pub fn set(&mut self, i: usize, j: usize, val: i32) {
        if i < self.source_rank && j < self.target_rank {
            self.matrix[i * self.target_rank + j] = val;
        }
    }

    /// Entry `(i, j)` (0 out of range).
    pub fn get(&self, i: usize, j: usize) -> i32 {
        if i < self.source_rank && j < self.target_rank {
            self.matrix[i * self.target_rank + j]
        } else {
            0
        }
    }

    /// The map as a matrix acting on column vectors (`target_rank` rows,
    /// `source_rank` columns).
    pub fn to_columns(&self) -> Vec<Vec<i64>> {
        (0..self.target_rank)
            .map(|j| (0..self.source_rank).map(|i| self.get(i, j) as i64).collect())
            .collect()
    }

    /// Rank of the map between free modules.
    pub fn rank(&self) -> Option<usize> {
        smith_form(&self.to_columns(), self.source_rank).ok().map(|s| s.rank())
    }

    /// Injective as a map `Z^source → Z^target` (full column rank).
    pub fn is_injective(&self) -> bool {
        self.rank() == Some(self.source_rank)
    }

    /// Surjective as a map `Z^source → Z^target` (full row rank and a
    /// torsion-free cokernel).
    pub fn is_surjective(&self) -> bool {
        smith_form(&self.to_columns(), self.source_rank)
            .map(|s| s.rank() == self.target_rank && s.is_torsion_free())
            .unwrap_or(false)
    }

    /// Is every entry zero?
    pub fn is_zero(&self) -> bool {
        self.matrix.iter().all(|&e| e == 0)
    }
}

/// `g ∘ f` (apply `f`, then `g`). `None` if the ranks do not chain or an
/// entry overflows `i32`.
pub fn compose_tor_maps(f: &ModuleMap, g: &ModuleMap) -> Option<ModuleMap> {
    if f.target_rank != g.source_rank {
        return None;
    }
    let mut result = ModuleMap::new(f.source_rank, g.target_rank);
    for i in 0..f.source_rank {
        for k in 0..g.target_rank {
            let mut sum = 0i64;
            for j in 0..f.target_rank {
                sum = sum.checked_add(f.get(i, j) as i64 * g.get(j, k) as i64)?;
            }
            result.set(i, k, i32::try_from(sum).ok()?);
        }
    }
    Some(result)
}

/// Reduce each column of `map` modulo the order of the corresponding
/// generator of `target` (torsion generators first, then free).
pub fn reduce_mod_target(map: &ModuleMap, target: &TorGroup) -> ModuleMap {
    let orders = target.torsion_orders();
    let mut out = map.clone();
    for i in 0..map.source_rank {
        for (j, &order) in orders.iter().enumerate() {
            out.set(i, j, (map.get(i, j) as i64).rem_euclid(order as i64) as i32);
        }
    }
    out
}

/// Lift `f0: P_0 → P'_0` (rows `P'_0`, columns `P_0`) to a chain map between
/// presentations/resolutions. Returns `F_k` for every `k` in `P`. Fails if
/// `f0` does not respect the relations of `M`.
pub fn lift_chain_map(
    p: &ProjectiveResolution,
    target: &ProjectiveResolution,
    f0: &[Vec<i64>],
) -> Result<Vec<Vec<Vec<i64>>>, String> {
    if p.augmentation.is_some() || target.augmentation.is_some() {
        return Err("lifting needs presentations (M = coker d_1, no augmentation)".into());
    }
    let (pr, pd) = resolution_data(p);
    let (qr, qd) = resolution_data(target);
    if pr.is_empty() || qr.is_empty() {
        return Err("empty resolution".into());
    }
    if f0.len() != qr[0] || f0.iter().any(|row| row.len() != pr[0]) {
        return Err(format!("f0 must be {} × {}", qr[0], pr[0]));
    }
    let mut maps = vec![f0.to_vec()];
    for k in 1..pr.len() {
        let rhs = multiply(&maps[k - 1], pr[k - 1], &pd[k - 1], pr[k]).map_err(|e| e.to_string())?;
        if k >= qr.len() {
            if !is_zero(&rhs) {
                return Err(format!("f does not lift: F_{} ∘ d_{k} ≠ 0 but P'_{k} = 0", k - 1));
            }
            maps.push(Vec::new());
            continue;
        }
        let mut fk = vec![vec![0i64; pr[k]]; qr[k]];
        for col in 0..pr[k] {
            let column: Vec<i64> = rhs.iter().map(|r| r[col]).collect();
            let x = solve(&qd[k - 1], qr[k], &column)
                .map_err(|e| e.to_string())?
                .ok_or_else(|| format!("f does not respect the relations: no lift at degree {k}"))?;
            for (row, v) in x.into_iter().enumerate() {
                fk[row][col] = v;
            }
        }
        maps.push(fk);
    }
    Ok(maps)
}

/// Explicit generators of `H_n` of a free complex.
struct HomologyBasis {
    kernel: Vec<Vec<i64>>,
    k: usize,
    u: Vec<Vec<i64>>,
    generators: Vec<usize>,
    orders: Vec<Option<u64>>,
    vectors: Vec<Vec<i64>>,
}

fn homology_basis(complex: &TensoredComplex, n: usize) -> Result<HomologyBasis, String> {
    let c_n = complex.total_rank_at(n);
    let kernel_vectors = smith_form(&complex.differential_matrix(n), c_n)
        .map_err(|e| e.to_string())?
        .kernel_basis;
    let k = kernel_vectors.len();
    let kernel: Vec<Vec<i64>> = (0..c_n)
        .map(|row| kernel_vectors.iter().map(|v| v[row]).collect())
        .collect();

    let c_next = complex.total_rank_at(n + 1);
    let d_next = complex.differential_matrix(n + 1);
    let mut b = vec![vec![0i64; c_next]; k];
    for col in 0..c_next {
        let column: Vec<i64> = d_next.iter().map(|r| r[col]).collect();
        let coords = solve(&kernel, k, &column)
            .map_err(|e| e.to_string())?
            .ok_or_else(|| format!("D_{} does not land in ker D_{n}", n + 1))?;
        for (row, x) in coords.into_iter().enumerate() {
            b[row][col] = x;
        }
    }
    let s = smith_decomposition(&b, c_next).map_err(|e| e.to_string())?;
    let mut generators = Vec::new();
    let mut orders = Vec::new();
    for (g, &d) in s.diagonal.iter().enumerate() {
        if d.unsigned_abs() > 1 {
            generators.push(g);
            orders.push(Some(d.unsigned_abs()));
        }
    }
    for g in s.rank()..k {
        generators.push(g);
        orders.push(None);
    }
    let vectors = generators
        .iter()
        .map(|&g| {
            let column: Vec<i64> = (0..k).map(|row| s.u_inv[row][g]).collect();
            apply(&kernel, k, &column).map_err(|e| e.to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    Ok(HomologyBasis {
        kernel,
        k,
        u: s.u,
        generators,
        orders,
        vectors,
    })
}

impl HomologyBasis {
    fn coordinates(&self, cycle: &[i64]) -> Result<Vec<i64>, String> {
        let y = solve(&self.kernel, self.k, cycle)
            .map_err(|e| e.to_string())?
            .ok_or("image is not a cycle")?;
        let z = apply(&self.u, self.k, &y).map_err(|e| e.to_string())?;
        Ok(self
            .generators
            .iter()
            .zip(&self.orders)
            .map(|(&g, order)| match order {
                Some(o) => z[g].rem_euclid(*o as i64),
                None => z[g],
            })
            .collect())
    }

    fn group(&self, n: usize) -> TorGroup {
        let torsion: Vec<u64> = self.orders.iter().flatten().copied().collect();
        let rank = self.orders.iter().filter(|o| o.is_none()).count();
        TorGroup::from_invariants(TorIndex::new(n), rank, &torsion)
    }
}

/// The chain map `F ⊗ id_Q` on `Tot_n` (rows `Tot'_n`, columns `Tot_n`).
fn total_chain_map(
    source: &TensoredComplex,
    target: &TensoredComplex,
    lifts: &[Vec<Vec<i64>>],
    n: usize,
) -> Vec<Vec<i64>> {
    let mut phi = vec![vec![0i64; source.total_rank_at(n)]; target.total_rank_at(n)];
    for (a, fa) in lifts.iter().enumerate() {
        let (Some(src_off), Some(tgt_off)) = (source.block_offset(n, a), target.block_offset(n, a)) else {
            continue;
        };
        let qb = source.q_ranks[n - a];
        for (i2, row) in fa.iter().enumerate() {
            for (i, &c) in row.iter().enumerate() {
                if c == 0 {
                    continue;
                }
                for j in 0..qb {
                    phi[tgt_off + i2 * qb + j][src_off + i * qb + j] += c;
                }
            }
        }
    }
    phi
}

/// `f_*: Tor_n(M, N) → Tor_n(M', N)` in explicit generators.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InducedTorMap {
    /// The degree `n`.
    pub degree: usize,
    /// `Tor_n(M, N)`.
    pub source: TorGroup,
    /// `Tor_n(M', N)`.
    pub target: TorGroup,
    /// The map on generators (entries reduced modulo target orders).
    pub map: ModuleMap,
}

/// Compute `f_*` on `Tor_degree(M, N)` for `f: M → M'` given on generators
/// by `f0` (rows `P'_0`, columns `P_0`). `p` and `p_prime` must be
/// presentations; `q` resolves `N`.
pub fn induced_tor_map(
    p: &ProjectiveResolution,
    p_prime: &ProjectiveResolution,
    q: &ProjectiveResolution,
    f0: &[Vec<i64>],
    degree: usize,
) -> Result<InducedTorMap, String> {
    let lifts = lift_chain_map(p, p_prime, f0)?;
    let source = tensor_resolutions(p, q)?;
    let target = tensor_resolutions(p_prime, q)?;
    let hs = homology_basis(&source, degree)?;
    let ht = homology_basis(&target, degree)?;
    let phi = total_chain_map(&source, &target, &lifts, degree);
    let mut map = ModuleMap::new(hs.vectors.len(), ht.vectors.len());
    for (i, v) in hs.vectors.iter().enumerate() {
        let image = apply(&phi, source.total_rank_at(degree), v).map_err(|e| e.to_string())?;
        for (j, c) in ht.coordinates(&image)?.into_iter().enumerate() {
            map.set(i, j, i32::try_from(c).map_err(|_| "induced map entry overflows i32")?);
        }
    }
    Ok(InducedTorMap {
        degree,
        source: hs.group(degree),
        target: ht.group(degree),
        map,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn z_mod(n: i64) -> ProjectiveResolution {
        ProjectiveResolution::cyclic_resolution(n)
    }

    #[test]
    fn free_module_map_properties() {
        let mut iso = ModuleMap::new(2, 2);
        iso.set(0, 0, 1);
        iso.set(1, 1, 1);
        assert!(iso.is_injective() && iso.is_surjective());

        let mut doubling = ModuleMap::new(1, 1);
        doubling.set(0, 0, 2);
        assert!(doubling.is_injective());
        assert!(!doubling.is_surjective());

        let mut projection = ModuleMap::new(2, 1);
        projection.set(0, 0, 1);
        assert!(!projection.is_injective());
        assert!(projection.is_surjective());
        assert!(!ModuleMap::new(2, 2).is_injective());
    }

    #[test]
    fn composition_of_maps() {
        let mut f = ModuleMap::new(2, 3);
        f.set(0, 0, 1);
        f.set(1, 1, 1);
        let mut g = ModuleMap::new(3, 2);
        g.set(0, 0, 2);
        g.set(1, 1, 3);
        let gf = compose_tor_maps(&f, &g).unwrap();
        assert_eq!((gf.get(0, 0), gf.get(1, 1)), (2, 3));
        assert!(compose_tor_maps(&f, &f).is_none());
        let mut big = ModuleMap::new(1, 1);
        big.set(0, 0, i32::MAX);
        assert!(compose_tor_maps(&big, &big).is_none());
    }

    #[test]
    fn identity_induces_identity() {
        for degree in 0..2 {
            let m = induced_tor_map(&z_mod(4), &z_mod(4), &z_mod(6), &[vec![1]], degree).unwrap();
            assert_eq!(m.source.torsion_orders(), vec![2]);
            assert_eq!(m.map.matrix, vec![1], "degree {degree}");
        }
    }

    #[test]
    fn multiplication_by_two_kills_z2_tor() {
        for degree in 0..2 {
            let m = induced_tor_map(&z_mod(4), &z_mod(4), &z_mod(6), &[vec![2]], degree).unwrap();
            assert!(m.map.is_zero(), "degree {degree}: {:?}", m.map);
        }
    }

    #[test]
    fn inclusion_z2_into_z4() {
        let q = z_mod(2);
        let tor0 = induced_tor_map(&z_mod(2), &z_mod(4), &q, &[vec![2]], 0).unwrap();
        assert!(tor0.map.is_zero());
        let tor1 = induced_tor_map(&z_mod(2), &z_mod(4), &q, &[vec![2]], 1).unwrap();
        assert_eq!((tor1.source.torsion_orders(), tor1.target.torsion_orders()), (vec![2], vec![2]));
        assert_eq!(tor1.map.matrix, vec![1]);
    }

    #[test]
    fn composition_is_preserved() {
        let (m, q) = (z_mod(8), z_mod(4));
        for degree in 0..2 {
            let f = induced_tor_map(&m, &m, &q, &[vec![3]], degree).unwrap();
            let g = induced_tor_map(&m, &m, &q, &[vec![5]], degree).unwrap();
            let gf = induced_tor_map(&m, &m, &q, &[vec![15]], degree).unwrap();
            let composed = reduce_mod_target(&compose_tor_maps(&f.map, &g.map).unwrap(), &gf.target);
            assert_eq!(composed, gf.map, "degree {degree}");
        }
    }

    #[test]
    fn ill_defined_maps_are_rejected() {
        let err = induced_tor_map(&z_mod(2), &z_mod(4), &z_mod(2), &[vec![1]], 0).unwrap_err();
        assert!(err.contains("relations"), "{err}");
        assert!(lift_chain_map(&z_mod(2), &z_mod(4), &[vec![1, 0]]).is_err());
        assert!(lift_chain_map(&ProjectiveResolution::free_of_rank_one(), &z_mod(4), &[vec![1]]).is_err());
    }
}

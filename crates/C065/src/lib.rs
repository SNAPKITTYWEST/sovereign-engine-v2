//! spectrum_order
//!
//! Topological ordering on prime spectra.
//! Specialization order: `P ≤ Q` iff `P ⊆ Q` (Q is a specialization of P,
//! i.e. Q lies in the closure of {P}). For Spec(Z) this is exact:
//! `(p) ⊆ (q)` iff `q | p`, so `(0)` lies below every point.
//! Used for the Zariski topology, whose closed sets are the sets closed
//! under specialization.

#![warn(missing_docs)]

use spectrum_definition::Spectrum;
use std::collections::BTreeSet;

/// Specialization preorder on spectrum
#[derive(Clone, Debug)]
pub struct SpecializationPreorder {
    /// Ordered pairs (p, q) where p ≤ q in specialization order
    order: BTreeSet<(u64, u64)>,
}

impl SpecializationPreorder {
    /// Create preorder from spectrum
    pub fn from_spectrum(spec: &Spectrum) -> Self {
        let mut order = BTreeSet::new();
        let primes: Vec<u64> = spec.primes.iter().copied().collect();

        for &p in &primes {
            for &q in &primes {
                if spec.specializes(p, q) {
                    order.insert((p, q));
                }
            }
        }

        Self { order }
    }

    /// `p ≤ q`: `(p) ⊆ (q)`, i.e. `q` is a specialization of `p`.
    pub fn le(&self, p: u64, q: u64) -> bool {
        self.order.contains(&(p, q))
    }

    /// Get all elements ≥ p
    pub fn upper_set(&self, p: u64) -> BTreeSet<u64> {
        self.order
            .iter()
            .filter(|(a, _)| a == &p)
            .map(|(_, b)| *b)
            .collect()
    }

    /// Get all elements ≤ q
    pub fn lower_set(&self, q: u64) -> BTreeSet<u64> {
        self.order
            .iter()
            .filter(|(_, b)| b == &q)
            .map(|(a, _)| *a)
            .collect()
    }

    /// Get minimal elements of a subset
    pub fn minimal_elements(&self, subset: &BTreeSet<u64>) -> BTreeSet<u64> {
        subset
            .iter()
            .filter(|&p| {
                subset
                    .iter()
                    .all(|&q| q == *p || !self.le(q, *p))
            })
            .copied()
            .collect()
    }

    /// Get maximal elements of a subset
    pub fn maximal_elements(&self, subset: &BTreeSet<u64>) -> BTreeSet<u64> {
        subset
            .iter()
            .filter(|&p| {
                subset
                    .iter()
                    .all(|&q| q == *p || !self.le(*p, q))
            })
            .copied()
            .collect()
    }
}

/// Zariski topology on spectrum
#[derive(Clone, Debug)]
pub struct ZariskiTopology {
    preorder: SpecializationPreorder,
}

impl ZariskiTopology {
    /// Create Zariski topology from spectrum
    pub fn from_spectrum(spec: &Spectrum) -> Self {
        Self {
            preorder: SpecializationPreorder::from_spectrum(spec),
        }
    }

    /// Closed sets are closed under specialization: if `P ∈ U` and `P ≤ Q`
    /// then `Q ∈ U`.
    pub fn is_closed(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> bool {
        for &p in subset {
            if !spectrum.contains_prime(p) {
                return false;
            }
        }
        // Check down-set property
        for &p in subset {
            for &q in &spectrum.primes {
                if self.preorder.le(p, q) && !subset.contains(&q) {
                    return false;
                }
            }
        }
        true
    }

    /// Open sets are complements of closed sets
    pub fn is_open(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> bool {
        let complement: BTreeSet<u64> = spectrum
            .primes
            .iter()
            .copied()
            .filter(|p| !subset.contains(p))
            .collect();
        self.is_closed(&complement, spectrum)
    }

    /// Get neighborhood of point p
    pub fn neighborhood(&self, p: u64) -> BTreeSet<u64> {
        self.preorder.lower_set(p)
    }

    /// Get closure of a subset
    pub fn closure(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> BTreeSet<u64> {
        let mut closure = subset.clone();
        let mut changed = true;

        while changed {
            changed = false;
            for &p in &spectrum.primes {
                if closure.contains(&p) {
                    for &q in &spectrum.primes {
                        if self.preorder.le(p, q) && !closure.contains(&q) {
                            closure.insert(q);
                            changed = true;
                        }
                    }
                }
            }
        }

        closure
    }

    /// Get interior of a subset
    pub fn interior(&self, subset: &BTreeSet<u64>, spectrum: &Spectrum) -> BTreeSet<u64> {
        subset
            .iter()
            .copied()
            .filter(|&p| {
                spectrum
                    .primes
                    .iter()
                    .all(|&q| !self.preorder.le(p, q) || subset.contains(&q))
            })
            .collect()
    }

    /// Get the specialization preorder
    pub fn preorder(&self) -> &SpecializationPreorder {
        &self.preorder
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_specialization_preorder() {
        let spec = Spectrum::new(vec![0, 2, 3, 5, 6]);
        let preorder = SpecializationPreorder::from_spectrum(&spec);
        assert!(preorder.le(2, 2));
        assert!(preorder.le(0, 2) && preorder.le(0, 5));
        assert!(!preorder.le(2, 0));
        assert!(!preorder.le(2, 3));
        assert!(!preorder.le(6, 2), "6 is not prime, so it is not in the spectrum");
        let everything: BTreeSet<u64> = spec.primes.iter().copied().collect();
        assert_eq!(preorder.minimal_elements(&everything), [0].into_iter().collect());
        assert_eq!(preorder.maximal_elements(&everything), [2, 3, 5].into_iter().collect());
    }

    #[test]
    fn test_zariski_topology() {
        let spec = Spectrum::new(vec![0, 2, 3, 5]);
        let topo = ZariskiTopology::from_spectrum(&spec);
        let set = |xs: &[u64]| xs.iter().copied().collect::<BTreeSet<u64>>();
        assert!(topo.is_closed(&set(&[2]), &spec), "closed points are closed");
        assert!(!topo.is_closed(&set(&[0]), &spec), "the generic point is not closed");
        assert_eq!(topo.closure(&set(&[0]), &spec), set(&[0, 2, 3, 5]));
        assert!(topo.is_open(&set(&[0, 3, 5]), &spec));
        assert!(!topo.is_open(&set(&[2]), &spec), "a non-empty open set contains the generic point");
        assert_eq!(topo.interior(&set(&[0, 2]), &spec), set(&[2]));
    }

    #[test]
    fn test_closure() {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let topo = ZariskiTopology::from_spectrum(&spec);

        let mut subset = BTreeSet::new();
        subset.insert(2);

        let closure = topo.closure(&subset, &spec);
        assert!(closure.contains(&2));
    }

    #[test]
    fn test_neighborhood() {
        let spec = Spectrum::new(vec![2, 3, 5]);
        let topo = ZariskiTopology::from_spectrum(&spec);

        let neighborhood = topo.neighborhood(3);
        assert!(neighborhood.contains(&3)); // reflexivity
    }
}

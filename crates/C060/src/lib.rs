//! tor_tests_integration
//!
//! Integration scenarios for the Tor tier (C051–C059), each checked against
//! known values: `Z/m ⊗ Z/n = Z/gcd(m,n)`, `Tor_1(Z/m, Z/n) = Z/gcd(m,n)`,
//! vanishing of higher Tor, agreement of `Tor_0` with the tensor product, and
//! functoriality of induced maps.

#![warn(missing_docs)]

pub use derived_homology::compute_tor_from_resolution;
use derived_homology::{tensor_resolutions, tor_of, verify_tor_computation};
pub use functoriality_of_tor::ModuleMap;
use functoriality_of_tor::{compose_tor_maps, induced_tor_map, reduce_mod_target};
pub use resolution_tensored::TensoredComplex;
use resolution_tensored::TensoredComplexProperties;
pub use tensor_product_module::TensorProductModule;
pub use tor_chain_complex_interface::TorChainComplexData;
pub use tor_functor_definition::TorComputation;
use tor_functor_definition::ProjectiveResolution;
pub use tor_higher_degrees::is_short_exact_sequence;
use tor_higher_degrees::tor_sequence;
pub use tor_invariants_computation::compute_betti_numbers;
use tor_invariants_computation::global_dimension;
pub use tor_zero_structure::analyze_tor_zero;
use tor_zero_structure::verify_tor_zero_universal_property;

/// Outcome of one scenario.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScenarioResult {
    /// Scenario name.
    pub name: &'static str,
    /// Failure description, if any.
    pub failure: Option<String>,
}

/// Outcome of all scenarios.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TorIntegrationReport {
    /// Per-scenario results.
    pub scenarios: Vec<ScenarioResult>,
}

impl TorIntegrationReport {
    /// True iff every scenario passed.
    pub fn all_passed(&self) -> bool {
        self.scenarios.iter().all(|s| s.failure.is_none())
    }

    /// Failed scenarios.
    pub fn failures(&self) -> Vec<&ScenarioResult> {
        self.scenarios.iter().filter(|s| s.failure.is_some()).collect()
    }
}

fn z_mod(n: i64) -> ProjectiveResolution {
    ProjectiveResolution::cyclic_resolution(n)
}

fn gcd(a: i64, b: i64) -> u64 {
    let (mut a, mut b) = (a.unsigned_abs(), b.unsigned_abs());
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

fn ensure(condition: bool, message: String) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(message)
    }
}

const PAIRS: [(i64, i64); 5] = [(4, 6), (2, 3), (12, 18), (9, 9), (5, 7)];

fn tensor_of_cyclic_groups() -> Result<(), String> {
    for (m, n) in PAIRS {
        let module = TensorProductModule::from_presentations(1, &[vec![m]], 1, 1, &[vec![n]], 1)
            .map_err(|e| e.to_string())?;
        let group = analyze_tor_zero(&module)?;
        let g = gcd(m, n);
        let expected: Vec<u64> = if g > 1 { vec![g] } else { vec![] };
        ensure(
            group.rank == 0 && group.torsion_orders() == expected,
            format!("Z/{m} ⊗ Z/{n} gave {group:?}"),
        )?;
    }
    Ok(())
}

fn tor1_of_cyclic_groups() -> Result<(), String> {
    for (m, n) in PAIRS {
        let tor = tor_of(&z_mod(m), &z_mod(n))?;
        let g = gcd(m, n);
        let expected: Vec<u64> = if g > 1 { vec![g] } else { vec![] };
        let tor1 = tor.tor(1).ok_or("missing Tor_1")?;
        ensure(
            tor1.rank == 0 && tor1.torsion_orders() == expected,
            format!("Tor_1(Z/{m}, Z/{n}) gave {tor1:?}"),
        )?;
        ensure(
            tor.tor(2).map_or(true, |g| g.is_trivial()),
            format!("Tor_2(Z/{m}, Z/{n}) should vanish over Z"),
        )?;
        ensure(
            global_dimension(&tor) <= Some(1),
            format!("Tor dimension above 1 for Z/{m}, Z/{n}"),
        )?;
    }
    Ok(())
}

fn tor_zero_matches_tensor_product() -> Result<(), String> {
    for (m, n) in PAIRS {
        ensure(
            verify_tor_zero_universal_property(&z_mod(m), &z_mod(n))?,
            format!("Tor_0(Z/{m}, Z/{n}) disagrees with Z/{m} ⊗ Z/{n}"),
        )?;
    }
    Ok(())
}

fn free_arguments_kill_higher_tor() -> Result<(), String> {
    let tor = tor_of(&z_mod(6), &ProjectiveResolution::free_of_rank_one())?;
    ensure(is_short_exact_sequence(&tor_sequence(&tor)), "Tor_1(Z/6, Z) should vanish".into())?;
    let data = TorChainComplexData::from_resolution(z_mod(0))?;
    ensure(compute_betti_numbers(&data.tor).beta(0) == 1, "Tor_0(Z, Z) should be Z".into())
}

fn tensored_complex_is_verified() -> Result<(), String> {
    let complex = tensor_resolutions(&z_mod(4), &z_mod(6))?;
    ensure(complex.verify_complex(), "Tot(P ⊗ Q) fails D² = 0".into())?;
    let tor = compute_tor_from_resolution(&complex)?;
    ensure(verify_tor_computation(&complex, &tor), "Tor recomputation disagrees".into())?;
    let props = TensoredComplexProperties::analyze(&complex).map_err(|e| e.to_string())?;
    ensure(!props.is_exact(), "Tot for Z/4, Z/6 should not be exact".into())
}

fn functoriality_laws_hold() -> Result<(), String> {
    let (m, q) = (z_mod(8), z_mod(4));
    for degree in 0..2 {
        let id = induced_tor_map(&m, &m, &q, &[vec![1]], degree)?;
        let identity_ok = (0..id.map.source_rank).all(|i| {
            (0..id.map.target_rank).all(|j| id.map.get(i, j) == i32::from(i == j))
        });
        ensure(identity_ok, format!("id_* is not the identity in degree {degree}"))?;
        let f = induced_tor_map(&m, &m, &q, &[vec![3]], degree)?;
        let g = induced_tor_map(&m, &m, &q, &[vec![5]], degree)?;
        let gf = induced_tor_map(&m, &m, &q, &[vec![15]], degree)?;
        let composed = compose_tor_maps(&f.map, &g.map).ok_or("composition failed")?;
        ensure(
            reduce_mod_target(&composed, &gf.target) == gf.map,
            format!("(g∘f)_* ≠ g_* ∘ f_* in degree {degree}"),
        )?;
    }
    Ok(())
}

/// Run every scenario.
pub fn run_tor_integration() -> TorIntegrationReport {
    type Scenario = fn() -> Result<(), String>;
    let scenarios: [(&'static str, Scenario); 6] = [
        ("tensor_of_cyclic_groups", tensor_of_cyclic_groups),
        ("tor1_of_cyclic_groups", tor1_of_cyclic_groups),
        ("tor_zero_matches_tensor_product", tor_zero_matches_tensor_product),
        ("free_arguments_kill_higher_tor", free_arguments_kill_higher_tor),
        ("tensored_complex_is_verified", tensored_complex_is_verified),
        ("functoriality_laws_hold", functoriality_laws_hold),
    ];
    TorIntegrationReport {
        scenarios: scenarios
            .iter()
            .map(|&(name, run)| ScenarioResult {
                name,
                failure: run().err(),
            })
            .collect(),
    }
}

/// True iff every Tor-tier scenario passes.
pub fn tier5_integration_test() -> bool {
    run_tor_integration().all_passed()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_scenario_passes() {
        let report = run_tor_integration();
        assert_eq!(report.scenarios.len(), 6);
        assert!(report.all_passed(), "{:?}", report.failures());
        assert!(tier5_integration_test());
    }

    #[test]
    fn module_map_is_available() {
        let mut map = ModuleMap::new(2, 3);
        map.set(0, 0, 1);
        map.set(1, 1, 1);
        assert!(map.is_injective());
        assert!(!map.is_surjective());
    }
}

//! magma-safety — MAGMA Core electromagnetic safety and certificate library.
//!
//! Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
//!
//! Implements:
//!   1. Biot–Savart mutual-influence matrix computation
//!   2. Compile-time safety certificate: A·I_max < H_dist (component-wise)
//!   3. SHA-256 netlist commitment
//!   4. Ed25519 signed certificate pipeline
//!
//! Core theorem (zero-sorry proof target in Lean 4):
//!   A * Imax < Hdist  →  ∀ I, |I| ≤ Imax → |A·I| < Hdist
//!
//! Three-layer boundary:
//!   safety layer   : row_bound + check_safety (strict < Hdist)
//!   certificate    : canonical netlist hash + margin commitment
//!   crypto layer   : Ed25519 signing + domain-separated payload
//!
//! Connection to magma_666.adb:
//!   Core_State.Valid → check_safety returns Ok
//!   M.Verify(Core)  → all cores satisfy Ones ≤ 4096 (structural)
//!   M.Imaginary(X)  → complement; maps to NAND transform in CCE

use sha2::{Digest, Sha256};
use std::fmt;

pub type Scalar = f64;
pub type Vec3   = [Scalar; 3];

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Wire {
    pub id:        u32,
    pub i_max:     Scalar,
    pub influence: Vec3,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Core {
    pub id:     u32,
    pub h_dist: Scalar,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Netlist {
    pub wires:  Vec<Wire>,
    pub cores:  Vec<Core>,
    pub matrix: Vec<Vec<Scalar>>,   // rows = cores, cols = wires
}

#[derive(Clone, Debug, PartialEq)]
pub struct SafetyCertificate {
    pub version: u32,
    pub digest:  [u8; 32],
    pub margins: Vec<Scalar>,
}

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub enum Error {
    InvalidInput(&'static str),
    DimensionMismatch,
    Unsafe { core: u32, bound: Scalar, limit: Scalar },
    BadSignature,
    NonFinite,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::InvalidInput(s)              => write!(f, "invalid input: {s}"),
            Error::DimensionMismatch            => write!(f, "dimension mismatch"),
            Error::Unsafe { core, bound, limit} => write!(f, "core {core} unsafe: {bound} >= {limit}"),
            Error::BadSignature                 => write!(f, "invalid certificate signature"),
            Error::NonFinite                    => write!(f, "non-finite value"),
        }
    }
}

impl std::error::Error for Error {}

fn finite(x: Scalar) -> Result<Scalar, Error> {
    if x.is_finite() { Ok(x) } else { Err(Error::NonFinite) }
}

// ---------------------------------------------------------------------------
// Geometry
// ---------------------------------------------------------------------------

pub fn norm(v: Vec3) -> Scalar {
    (v[0]*v[0] + v[1]*v[1] + v[2]*v[2]).sqrt()
}

pub fn cross(a: Vec3, b: Vec3) -> Vec3 {
    [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
}

/// Conservative Biot–Savart influence for a single wire segment.
/// Returns |H| / I (A/m per amp) at point r.
pub fn influence_segment(a: Vec3, b: Vec3, r: Vec3) -> Result<Vec3, Error> {
    for x in a.into_iter().chain(b).chain(r) { finite(x)?; }
    let d    = [b[0]-a[0], b[1]-a[1], b[2]-a[2]];
    let q    = [r[0]-a[0], r[1]-a[1], r[2]-a[2]];
    let mid  = [(a[0]+b[0])*0.5, (a[1]+b[1])*0.5, (a[2]+b[2])*0.5];
    let qmid = [r[0]-mid[0], r[1]-mid[1], r[2]-mid[2]];
    let rad  = norm(qmid);
    if rad <= 0.0 { return Err(Error::InvalidInput("wire intersects core")); }
    let c     = cross(d, q);
    let scale = 1.0 / (4.0 * std::f64::consts::PI * rad.powi(3));
    Ok([c[0]*scale, c[1]*scale, c[2]*scale])
}

// ---------------------------------------------------------------------------
// Safety check
// ---------------------------------------------------------------------------

/// Σ_w |A_{c,w}| · I_w_max  (upper bound on |H_c|)
pub fn row_bound(row: &[Scalar], currents: &[Scalar]) -> Result<Scalar, Error> {
    if row.len() != currents.len() { return Err(Error::DimensionMismatch); }
    row.iter().zip(currents).try_fold(0.0_f64, |s, (&a, &i)| {
        Ok(s + finite(a)?.abs() * finite(i)?.abs())
    })
}

/// Check safety for all cores. Returns safety margins (H_dist - bound) on Ok.
pub fn check_safety(net: &Netlist) -> Result<Vec<Scalar>, Error> {
    if net.matrix.len() != net.cores.len() { return Err(Error::DimensionMismatch); }
    for w in &net.wires {
        if !w.i_max.is_finite() || w.i_max < 0.0 {
            return Err(Error::InvalidInput("Imax must be finite and non-negative"));
        }
    }
    let currents: Vec<_> = net.wires.iter().map(|w| w.i_max).collect();
    net.matrix.iter().enumerate().map(|(i, row)| {
        let bound = row_bound(row, &currents)?;
        let limit = finite(net.cores[i].h_dist)?;
        if limit <= 0.0 { return Err(Error::InvalidInput("Hdist must be positive")); }
        if !(bound < limit) {
            return Err(Error::Unsafe { core: net.cores[i].id, bound, limit });
        }
        Ok(limit - bound)
    }).collect()
}

// ---------------------------------------------------------------------------
// Certificate
// ---------------------------------------------------------------------------

pub fn canonical_bytes(net: &Netlist) -> Result<Vec<u8>, Error> {
    let mut out = Vec::new();
    out.extend_from_slice(b"MAGMA/1\0");
    for c in &net.cores {
        out.extend_from_slice(&c.id.to_le_bytes());
        out.extend_from_slice(&finite(c.h_dist)?.to_bits().to_le_bytes());
    }
    for w in &net.wires {
        out.extend_from_slice(&w.id.to_le_bytes());
        out.extend_from_slice(&finite(w.i_max)?.to_bits().to_le_bytes());
        for x in w.influence { out.extend_from_slice(&finite(x)?.to_bits().to_le_bytes()); }
    }
    for row in &net.matrix {
        out.extend_from_slice(&(row.len() as u64).to_le_bytes());
        for x in row { out.extend_from_slice(&finite(*x)?.to_bits().to_le_bytes()); }
    }
    Ok(out)
}

pub fn digest(net: &Netlist) -> Result<[u8; 32], Error> {
    Ok(Sha256::digest(canonical_bytes(net)?).into())
}

pub fn certificate(net: &Netlist) -> Result<SafetyCertificate, Error> {
    Ok(SafetyCertificate { version: 1, digest: digest(net)?, margins: check_safety(net)? })
}

pub fn verify_certificate(net: &Netlist, cert: &SafetyCertificate) -> Result<(), Error> {
    if cert.version != 1 || cert.digest != digest(net)? { return Err(Error::BadSignature); }
    let margins = check_safety(net)?;
    if margins.len() != cert.margins.len() { return Err(Error::BadSignature); }
    if margins.iter().zip(&cert.margins).any(|(a, b)| a.to_bits() != b.to_bits()) {
        return Err(Error::BadSignature);
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Crypto (Ed25519)
// ---------------------------------------------------------------------------

pub mod crypto {
    use super::*;
    use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};

    fn payload(cert: &SafetyCertificate) -> Vec<u8> {
        let mut p = Vec::new();
        p.extend_from_slice(b"MAGMA-CERT/v1\0");
        p.extend_from_slice(&cert.version.to_le_bytes());
        p.extend_from_slice(&cert.digest);
        for x in &cert.margins { p.extend_from_slice(&x.to_bits().to_le_bytes()); }
        p
    }

    pub fn sign(net: &Netlist, key: &SigningKey) -> Result<(SafetyCertificate, Signature), Error> {
        let cert = certificate(net)?;
        Ok((cert.clone(), key.sign(&payload(&cert))))
    }

    pub fn verify(net: &Netlist, cert: &SafetyCertificate, sig: &Signature, key: &VerifyingKey) -> Result<(), Error> {
        if cert.version != 1 || cert.digest != digest(net)? { return Err(Error::BadSignature); }
        verify_certificate(net, cert)?;
        key.verify(&payload(cert), sig).map_err(|_| Error::BadSignature)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::SigningKey;
    use rand_core::OsRng;

    fn sample() -> Netlist {
        Netlist {
            wires:  vec![
                Wire { id: 1, i_max: 1.0, influence: [1.0, 0.0, 0.0] },
                Wire { id: 2, i_max: 2.0, influence: [0.0, 1.0, 0.0] },
            ],
            cores:  vec![Core { id: 7, h_dist: 10.0 }],
            matrix: vec![vec![1.0, 2.0]],
        }
    }

    #[test]
    fn bound_is_strict() {
        assert_eq!(check_safety(&sample()).unwrap(), vec![5.0]);
    }

    #[test]
    fn certificate_commits_netlist() {
        let n = sample();
        let c = certificate(&n).unwrap();
        assert_eq!(c.digest, digest(&n).unwrap());
        assert_eq!(c.margins[0], 5.0);
    }

    #[test]
    fn signed_certificate_verifies() {
        let n   = sample();
        let key = SigningKey::generate(&mut OsRng);
        let (c, s) = crypto::sign(&n, &key).unwrap();
        assert!(crypto::verify(&n, &c, &s, &key.verifying_key()).is_ok());
    }

    #[test]
    fn equality_at_limit_fails() {
        let mut n = sample();
        n.cores[0].h_dist = 5.0;
        assert!(matches!(check_safety(&n), Err(Error::Unsafe { .. })));
    }
}

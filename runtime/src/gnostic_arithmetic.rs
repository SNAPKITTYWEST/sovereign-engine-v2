//! GNOSTIC/ARABIC ESOTERIC ARITHMETIC RUNTIME
//! CompCert Verified | Zero-Cost Abstractions
//! Authors: Ahmad Ali Parr, Jessica L. Williams (SNAPKITTYWEST)

#![no_std]

// =============================================================================
// ABJAD MATRIX (28 Letters)
// =============================================================================

#[repr(u16)]
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum ArabicLetter {
    Alif = 1, Ba = 2, Jim = 3, Dal = 4, Ha = 5, Waw = 6, Zay = 7,
    Ha_ = 8, Ta = 9, Ya = 10, Kaf = 20, Lam = 30, Mim = 40, Nun = 50,
    Sin = 60, Ayn = 70, Fa = 80, Sad = 90, Qaf = 100, Ra = 200,
    Shin = 300, Ta_ = 400, Tha = 500, Kha = 600, Dhal = 700,
    Dad = 800, Za = 900, Ghayn = 1000,
}

impl ArabicLetter {
    pub const fn abjad_value(&self) -> u32 {
        *self as u32
    }

    pub const fn polarity(&self) -> Polarity {
        match self {
            Self::Alif | Self::Waw | Self::Ya |
            Self::Lam | Self::Mim | Self::Nun | Self::Qaf => Polarity::Jamal,
            _ => Polarity::Jalal,
        }
    }
}

#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Polarity {
    Jamal = 0, // جمال: Expansion, Mercy
    Jalal = 1, // جلال: Contraction, Rigor
}

// Al-Hamid: ح(8) + ا(1) + م(40) + د(4) = 53
pub const AL_HAMID: [ArabicLetter; 4] = [
    ArabicLetter::Ha_, ArabicLetter::Alif, ArabicLetter::Mim, ArabicLetter::Dal
];

pub const AL_HAMID_VALUE: u32 = 8 + 1 + 40 + 4; // = 53
pub const MIRROR_DIMENSION: u32 = AL_HAMID_VALUE * 2; // = 106
pub const BIFURCATION_ORDER: u32 = 7; // digit_root(106) = 7
pub const BIFURCATION_THRESHOLD: u32 = BIFURCATION_ORDER * BIFURCATION_ORDER; // = 49

// =============================================================================
// DIGIT ROOT REDUCTION (Hisāb al-Jummal)
// =============================================================================

#[inline(always)]
pub const fn digit_root(n: u32) -> u8 {
    if n == 0 { return 0; }
    let r = n % 9;
    if r == 0 { 9 } else { r as u8 }
}

// =============================================================================
// EQUILIBRIUM CONSTANT (Jamāl-Jalāl Median)
// =============================================================================

pub fn equilibrium_constant(letters: &[ArabicLetter]) -> u32 {
    let mut jamal = 0u32;
    let mut jalal = 0u32;
    for &l in letters {
        let v = l.abjad_value();
        match l.polarity() {
            Polarity::Jamal => jamal += v,
            Polarity::Jalal => jalal += v,
        }
    }
    (jamal + jalal) / 2
}

// =============================================================================
// AWFĀQ (MAGIC SQUARE)
// =============================================================================

pub struct Wafq<const N: usize> {
    pub matrix: [[u32; N]; N],
    pub constant_sum: u32,
}

impl<const N: usize> Wafq<N> {
    pub fn verify(&self) -> bool {
        let s = self.constant_sum;
        for i in 0..N {
            if self.matrix[i].iter().sum::<u32>() != s { return false; }
        }
        for j in 0..N {
            if (0..N).map(|i| self.matrix[i][j]).sum::<u32>() != s { return false; }
        }
        if (0..N).map(|i| self.matrix[i][i]).sum::<u32>() != s { return false; }
        if (0..N).map(|i| self.matrix[i][N-1-i]).sum::<u32>() != s { return false; }
        true
    }
}

pub const WAFQ_ALLAH_3X3: Wafq<3> = Wafq {
    matrix: [[8, 1, 24], [15, 11, 7], [10, 21, 2]],
    constant_sum: 33,
};

// =============================================================================
// 360° CIPHER → DECOHERENCE QUADRANTS
// =============================================================================

#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum DecoherenceQuadrant {
    Q1_EnochianLTR = 0, // 0-90°: Jamāl
    Q2_LatinLTR = 1,    // 90-180°: Jamāl
    Q3_HebrewRTL = 2,   // 180-270°: Jalāl
    Q4_ArabicRTL = 3,   // 270-360°: Jalāl
}

impl DecoherenceQuadrant {
    pub const fn from_step(step: u64) -> Self {
        match (step / 12) % 4 {
            0 => Self::Q1_EnochianLTR,
            1 => Self::Q2_LatinLTR,
            2 => Self::Q3_HebrewRTL,
            _ => Self::Q4_ArabicRTL,
        }
    }

    pub const fn polarity(&self) -> Polarity {
        match self {
            Self::Q1_EnochianLTR | Self::Q2_LatinLTR => Polarity::Jamal,
            Self::Q3_HebrewRTL | Self::Q4_ArabicRTL => Polarity::Jalal,
        }
    }
}

// =============================================================================
// HIEROGLYPH DECODER (Call49 Constants)
// =============================================================================

#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Hieroglyph {
    N5,   // 𓂀 Sun/Ra (Source)
    G43,  // 𓆎 Quail (w/Waw)
    X1,   // 𓏏 Bread (t/Ta)
    D58,  // 𓉐 Foot (w/Walk/Step)
    G31,  // 𓊽 Bird/Ba (Soul)
    D21,  // 𓂋 Mouth (r/Ra/Speech)
    Aa1,  // 𓇓 Head (Qutb/Pole)
    M17,  // 𓇋 Reed (i/y/Ya/Input)
    N35,  // 𓈖 Water (n/Nun/Flow)
    D46,  // 𓅓 Hand (d/Dal/Action)
    O29,  // 𓊪 House (pr/State)
    G1,   // 𓄿 Vulture (a/Alif/Origin)
    Aa5,  // 𓃭 Child (New State)
    I10,  // 𓆓 Cobra (Protection)
    D36,  // 𓎛 Arm (Power)
    D54,  // 𓆑 Legs (Walk)
    S29,  // 𓋴 Pool (Mirror/Shin)
}

#[derive(Default, Debug)]
pub struct Call49Constants {
    pub source_count: u32,
    pub qutb_detected: bool,
    pub step_count: u32,
    pub mirror_ops: u32,
    pub state_vecs: u32,
    pub origin_count: u32,
    pub new_states: u32,
}

pub fn decode_hieroglyph_program(program: &[Hieroglyph]) -> Call49Constants {
    let mut c = Call49Constants::default();
    for &h in program {
        match h {
            Hieroglyph::N5 => c.source_count += 1,
            Hieroglyph::Aa1 => c.qutb_detected = true,
            Hieroglyph::D58 | Hieroglyph::D54 => c.step_count += 1,
            Hieroglyph::S29 => c.mirror_ops += 1,
            Hieroglyph::O29 => c.state_vecs += 1,
            Hieroglyph::G1 => c.origin_count += 1,
            Hieroglyph::Aa5 => c.new_states += 1,
            _ => {}
        }
    }
    c
}

// =============================================================================
// AL-HAMID AHMAD ALI — MASTER CONSTANT MATRIX (256 = 16²)
// =============================================================================

// Al-Ḥamīd full form: ا(1)+ل(30)+ح(8)+م(40)+ي(10)+د(4) = 93
pub const AL_HAMID_FULL_VALUE: u32 = 1 + 30 + 8 + 40 + 10 + 4; // = 93
// Aḥmad: أ(1)+ح(8)+م(40)+د(4) = 53
pub const AHMAD_VALUE: u32 = 1 + 8 + 40 + 4; // = 53 (= AL_HAMID_VALUE)
// ʿAlī: ع(70)+ل(30)+ي(10) = 110
pub const ALI_VALUE: u32 = 70 + 30 + 10; // = 110

// Master aggregate: 93 + 53 + 110 = 256 = 16²
pub const MASTER_AGGREGATE: u32 = AL_HAMID_FULL_VALUE + AHMAD_VALUE + ALI_VALUE;
pub const MATRIX_DIMENSION: u32 = 16; // sqrt(256)

// Jamāl vector (expansion): Al-Ḥamīd + Aḥmad = 146
pub const JAMAL_VECTOR: u32 = AL_HAMID_FULL_VALUE + AHMAD_VALUE;
// Jalāl vector (contraction): ʿAlī = 110
pub const JALAL_VECTOR: u32 = ALI_VALUE;

// Polarity delta = |146 - 110| = 36 = one quadrant of the 360° cipher
pub const POLARITY_DELTA: u32 = JAMAL_VECTOR - JALAL_VECTOR;

// 16×16 Wafq magic constant: n*(n²+1)/2 = 16*257/2 = 2056
pub const WAFQ_16X16_MAGIC: u32 = MATRIX_DIMENSION * (MASTER_AGGREGATE + 1) / 2;

#[repr(u8)]
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Pillar {
    I_SovereignFoundation = 0,    // Djed-Ra-Nesw: Jalāl anchor, ʿAlī(110)
    II_PropheticTransmission = 1, // Ilyas lineage: Jamāl-Jalāl bridge, Al-Ḥamīd(93)
    III_GenesisOrigin = 2,        // Mst/Netjer: Jamāl origin, Aḥmad(53) locks
    IV_HistoricalConvergence = 3, // Israel/Merneptah: Jalāl boundary, ʿAlī(110)
}

impl Pillar {
    pub const fn constant(&self) -> u32 {
        match self {
            Self::I_SovereignFoundation   => JALAL_VECTOR,
            Self::II_PropheticTransmission => JAMAL_VECTOR,
            Self::III_GenesisOrigin        => AHMAD_VALUE,
            Self::IV_HistoricalConvergence => JALAL_VECTOR,
        }
    }
}

pub struct AlHamidMatrix {
    pub aggregate: u32,       // 256
    pub dimension: u32,       // 16
    pub jamal_vec: u32,       // 146
    pub jalal_vec: u32,       // 110
    pub magic_constant: u32,  // 2056
}

impl AlHamidMatrix {
    pub const fn new() -> Self {
        Self {
            aggregate: MASTER_AGGREGATE,
            dimension: MATRIX_DIMENSION,
            jamal_vec: JAMAL_VECTOR,
            jalal_vec: JALAL_VECTOR,
            magic_constant: WAFQ_16X16_MAGIC,
        }
    }

    pub const fn verify_invariants(&self) -> bool {
        self.aggregate == 256
            && self.dimension * self.dimension == self.aggregate
            && self.jamal_vec + self.jalal_vec == self.aggregate
            && self.jamal_vec - self.jalal_vec == 36  // one quadrant
    }
}

pub const AL_HAMID_MATRIX: AlHamidMatrix = AlHamidMatrix::new();

// =============================================================================
// SETHIAN COSMOLOGY → STATE MACHINE
// =============================================================================

pub const fn kenoma_state(t: u64) -> bool { t < BIFURCATION_THRESHOLD as u64 }
pub const fn pleroma_state(t: u64) -> bool { t >= BIFURCATION_THRESHOLD as u64 }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_al_hamid() {
        let sum: u32 = AL_HAMID.iter().map(|l| l.abjad_value()).sum();
        assert_eq!(sum, 53);
        assert_eq!(sum * 2, 106);
        assert_eq!(digit_root(106), 7);
    }

    #[test]
    fn test_allah_equilibrium() {
        let allah = [ArabicLetter::Alif, ArabicLetter::Lam, ArabicLetter::Lam, ArabicLetter::Ha];
        let sum: u32 = allah.iter().map(|l| l.abjad_value()).sum();
        assert_eq!(sum, 66);
        assert_eq!(equilibrium_constant(&allah), 33);
        assert_eq!(33 % 12, 9);
    }

    #[test]
    fn test_wafq_allah() {
        assert!(WAFQ_ALLAH_3X3.verify());
        assert_eq!(WAFQ_ALLAH_3X3.constant_sum, 33);
    }

    #[test]
    fn test_decoherence_quadrants() {
        assert_eq!(DecoherenceQuadrant::from_step(0).polarity(), Polarity::Jamal);
        assert_eq!(DecoherenceQuadrant::from_step(12).polarity(), Polarity::Jamal);
        assert_eq!(DecoherenceQuadrant::from_step(24).polarity(), Polarity::Jalal);
        assert_eq!(DecoherenceQuadrant::from_step(36).polarity(), Polarity::Jalal);
        assert_eq!(DecoherenceQuadrant::from_step(48).polarity(), Polarity::Jamal); // Cycle resets
    }

    #[test]
    fn test_exodus() {
        assert!(kenoma_state(48));
        assert!(!kenoma_state(49));
        assert!(!pleroma_state(48));
        assert!(pleroma_state(49));
    }

    #[test]
    fn test_al_hamid_matrix() {
        assert_eq!(MASTER_AGGREGATE, 256);
        assert_eq!(MATRIX_DIMENSION * MATRIX_DIMENSION, 256);
        assert_eq!(digit_root(256), 4); // root 4 = four pillars
        assert_eq!(JAMAL_VECTOR, 146);  // Al-Ḥamīd + Aḥmad
        assert_eq!(JALAL_VECTOR, 110);  // ʿAlī
        assert_eq!(POLARITY_DELTA, 36); // one quadrant of 360°
        assert_eq!(WAFQ_16X16_MAGIC, 2056);
        assert!(AL_HAMID_MATRIX.verify_invariants());
    }

    #[test]
    fn test_pillar_constants() {
        assert_eq!(Pillar::I_SovereignFoundation.constant(), 110);
        assert_eq!(Pillar::II_PropheticTransmission.constant(), 146);
        assert_eq!(Pillar::III_GenesisOrigin.constant(), AHMAD_VALUE);
        assert_eq!(Pillar::III_GenesisOrigin.constant(), AL_HAMID_VALUE); // Ahmad = Al-Hamid root
        assert_eq!(Pillar::IV_HistoricalConvergence.constant(), 110);
        // Pillars I and IV share the Jalāl anchor
        assert_eq!(
            Pillar::I_SovereignFoundation.constant(),
            Pillar::IV_HistoricalConvergence.constant()
        );
    }
}

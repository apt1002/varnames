//! The standard tables, embedded in the library.
//!
//! The bytes are compiled into the binary, so a program cannot start with the
//! wrong tables by accident: the digest below identifies them, and the loader
//! refuses bytes that do not match.  A crate built with different bytes panics
//! on first use rather than encode with the wrong tables.
//!
//! [`standard`] hands out the standard codec, and [`Codec::default`] is the
//! same codec.  A project that prefers its own model can load any `NVM1` file
//! with [`Model::from_bytes`] and hand it to [`Codec::new`].

use std::sync::OnceLock;

use crate::codec::Codec;
use crate::model::Model;
use crate::sha256;

/// The standard model of `standard/STANDARD.md`, built at `V = 8191`, `k = 32`,
/// `q = 1` (`standard/MODEL_FORMAT.md` §3).
pub static MODEL_BYTES: &[u8] = include_bytes!("../data/model.nvm1");

/// SHA-256 of [`MODEL_BYTES`].
pub const STANDARD_SHA256: &str =
    "976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79";

static STANDARD: OnceLock<Codec> = OnceLock::new();

fn load() -> Codec {
    let found = sha256::hex(MODEL_BYTES);
    assert_eq!(
        found, STANDARD_SHA256,
        "the embedded tables do not match their checksum"
    );
    Codec::new(Model::from_bytes(MODEL_BYTES).expect("the embedded tables are a valid NVM1 file"))
}

/// The standard codec, parsed on first use and cached.
///
/// The returned codec holds an [`Arc`](std::sync::Arc) to the cached model, so
/// calling this again is cheap and every codec shares the one copy of the
/// tables.
///
/// # Panics
///
/// If the embedded tables fail their checksum or do not parse.  That can only
/// happen if the crate was built with different bytes, which the crate's own
/// tests check against [`STANDARD_SHA256`].
pub fn standard() -> Codec {
    STANDARD.get_or_init(load).clone()
}

impl Default for Codec {
    /// The standard codec, [`standard`].
    fn default() -> Self {
        standard()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn digest_matches() {
        assert_eq!(sha256::hex(MODEL_BYTES), STANDARD_SHA256);
    }

    #[test]
    fn dimensions() {
        let codec = standard();
        let m = codec.model();
        assert_eq!(
            (m.num_words(), m.num_lefts(), m.num_rights_per_left()),
            (8_191, 32, 1)
        );
        assert_eq!(m.num_chars(), 63);
        assert_eq!(m.num_rules(), 8_128);
    }

    #[test]
    fn the_default_is_the_standard_codec() {
        let codec = standard();
        assert!(std::ptr::eq(codec.model(), Codec::default().model()));
        assert_eq!(
            Codec::default().encode("getUserName").unwrap(),
            124_101_637
        );
    }

    #[test]
    fn the_debug_form_is_the_models_shape() {
        assert_eq!(
            format!("{:?}", Codec::default()),
            "Codec(V=8191 k=32 q=1 alphabet=63 rules=8128 kq=32)"
        );
    }
}

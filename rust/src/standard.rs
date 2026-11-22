//! The standard tables, embedded in the library.
//!
//! The bytes are compiled into the binary, so a program cannot start with the
//! wrong tables by accident: the digest below identifies them, and
//! [`standard`] refuses bytes that do not match.
//!
//! [`standard`] hands out the tables; [`Model::default`] and [`Codec::default`]
//! are the same tables, ready to use.  A project that prefers its own model can
//! load any `NVM1` file with [`Model::from_bytes`].

use std::sync::OnceLock;

use crate::codec::Codec;
use crate::model::Model;
use crate::{sha256, Error};

/// The standard model of `standard/STANDARD.md`, built at `V = 8191`, `k = 32`,
/// `q = 1` (`standard/MODEL_FORMAT.md` §3).
pub static MODEL_BYTES: &[u8] = include_bytes!("../data/model.nvm1");

/// SHA-256 of [`MODEL_BYTES`].
pub const STANDARD_SHA256: &str =
    "976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79";

static STANDARD: OnceLock<Result<Model, Error>> = OnceLock::new();

fn load() -> Result<Model, Error> {
    let found = sha256::hex(MODEL_BYTES);
    if found != STANDARD_SHA256 {
        return Err(Error::Checksum {
            expected: STANDARD_SHA256,
            found,
        });
    }
    Model::from_bytes(MODEL_BYTES)
}

/// The standard model, parsed on first use and cached.
pub fn standard() -> Result<&'static Model, Error> {
    match STANDARD.get_or_init(load) {
        Ok(model) => Ok(model),
        Err(err) => Err(err.clone()),
    }
}

impl Default for Model {
    /// The standard model, cloned from [`standard`].
    ///
    /// # Panics
    ///
    /// If the embedded tables fail their checksum.  That can only happen if
    /// the crate was built with different bytes, which the crate's own tests
    /// check against [`STANDARD_SHA256`].
    fn default() -> Self {
        standard()
            .expect("the embedded tables match their checksum")
            .clone()
    }
}

impl Default for Codec {
    /// A codec over the standard model, [`Model::default`].
    ///
    /// The tables are parsed once and cached; each call clones them, so keep
    /// one codec and reuse it rather than building one per identifier.
    fn default() -> Self {
        Codec::new(Model::default())
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
        let m = standard().unwrap();
        assert_eq!(
            (m.num_words(), m.num_lefts(), m.num_rights_per_left()),
            (8_191, 32, 1)
        );
        assert_eq!(m.num_chars(), 63);
        assert_eq!(m.num_rules(), 8_128);
    }

    #[test]
    fn the_defaults_are_the_standard_tables() {
        let model = standard().expect("the embedded tables");
        assert_eq!(Model::default().num_words(), model.num_words());
        assert_eq!(Codec::default().model().num_words(), model.num_words());
        assert_eq!(
            Codec::default().encode("getUserName").unwrap(),
            124_101_637
        );
    }
}

//! The standard tables, embedded in the library.
//!
//! Both implementations default to the standardised tables but accept a custom
//! model file.  This module is the "default" half; use
//! [`crate::Model::from_bytes`] for the other.
//!
//! The bytes are compiled into the binary, so a program cannot start with the
//! wrong tables by accident: the digest below identifies them, and
//! [`standard`] refuses bytes that do not match.

use std::sync::OnceLock;

use crate::codec::Codec;
use crate::model::Model;
use crate::{sha256, Error};

/// The standard model of `docs/STANDARD.md`, built at `V = 8191`, `k = 32`,
/// `q = 1` (`docs/MODEL_FORMAT.md` §3).
pub static MODEL_BYTES: &[u8] = include_bytes!("../data/model.nvm1");

/// SHA-256 of [`MODEL_BYTES`].
pub const STANDARD_SHA256: &str =
    "976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79";

static STANDARD: OnceLock<Result<Codec, Error>> = OnceLock::new();

fn load() -> Result<Codec, Error> {
    let found = sha256::hex(MODEL_BYTES);
    if found != STANDARD_SHA256 {
        return Err(Error::Checksum {
            expected: STANDARD_SHA256,
            found,
        });
    }
    Ok(Codec::new(Model::from_bytes(MODEL_BYTES)?))
}

/// The standard codec, parsed on first use and cached.
pub fn standard() -> Result<&'static Codec, Error> {
    match STANDARD.get_or_init(load) {
        Ok(codec) => Ok(codec),
        Err(err) => Err(err.clone()),
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
        let codec = standard().unwrap();
        let m = codec.model();
        assert_eq!((m.v(), m.k(), m.q()), (8_191, 32, 1));
        assert_eq!(m.nchars(), 63);
        assert_eq!(m.rules().len(), 8_128);
    }
}

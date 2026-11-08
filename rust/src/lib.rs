//! Encode programming-language identifiers as 64- or 128-bit integers.
//!
//! A name becomes an integer by a bijection: the code is a Huffman-coded walk
//! over a pair-merge word list, and because the terminator is the all-zeros
//! codeword it costs nothing and the integer needs no length.  The map is
//! reversible — `decode(encode(name)) == name` — and short, common names land
//! in the low bits.
//!
//! ```
//! use varnames::standard;
//!
//! let codec = standard().expect("the embedded tables");
//! let code = codec.encode("getUserName").unwrap();
//! assert_eq!(code.bits, 27);
//! assert_eq!(codec.decode(code.value).unwrap(), "getUserName");
//! ```
//!
//! The tables ship inside the crate ([`standard`]); a project that prefers its
//! own can load any `NVM1` file with [`Model::from_bytes`] and hand it to
//! [`Codec::new`].

#![warn(missing_docs)]

use std::fmt;

pub mod bitio;
pub mod codec;
pub mod ladder;
pub mod model;
pub mod sha256;
pub mod standard;

pub use bitio::Bits;
pub use codec::{Code, Codec};
pub use model::{Model, Tree};
pub use standard::standard;

/// Everything that can go wrong encoding or decoding.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Error {
    /// The file does not start with `NVM1`.
    BadMagic,
    /// A section ends past the end of the file.
    Truncated(&'static str),
    /// A structural invariant of `MODEL_FORMAT.md` does not hold.
    Model(&'static str),
    /// The identifier uses a character outside the model's alphabet.
    UnknownCharacter(char),
    /// The code needs more bits than the caller asked for.
    CodeTooLong {
        /// The length that was needed.
        bits: usize,
    },
    /// The bits name a right cluster that has no words.
    EmptyCluster(u32),
    /// The bits do not reach the STOP leaf within the symbol budget.
    DoesNotTerminate,
    /// The embedded standard model is not the one this crate was built with.
    Checksum {
        /// The digest the crate expects.
        expected: &'static str,
        /// The digest of the bytes it found.
        found: String,
    },
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::BadMagic => write!(f, "not an NVM1 model"),
            Error::Truncated(what) => write!(f, "{what}"),
            Error::Model(what) => write!(f, "{what}"),
            Error::UnknownCharacter(c) => {
                write!(f, "character {c:?} is not in the model's alphabet")
            }
            Error::CodeTooLong { bits } => write!(
                f,
                "the code needs {bits} bits, more than the 128 this call accepts"
            ),
            Error::EmptyCluster(cluster) => {
                write!(f, "right cluster {cluster} is empty")
            }
            Error::DoesNotTerminate => write!(f, "the identifier does not terminate"),
            Error::Checksum { expected, found } => write!(
                f,
                "the standard model does not match its checksum: {found} != {expected}"
            ),
        }
    }
}

impl std::error::Error for Error {}

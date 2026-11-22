//! Encode programming-language identifiers as 64- or 128-bit integers.
//!
//! The encoding is reversible — `decode(encode(name)) == name`.
//! The encoding is little-endian — short, common names land in the low bits.
//!
//! ```
//! use varnames::Codec;
//!
//! let codec = Codec::default();
//! let bits = codec.encode_bits("getUserName").unwrap();
//! assert_eq!(bits.len(), 27);
//! assert_eq!(codec.decode_bits(&bits).unwrap(), "getUserName");
//! assert_eq!(codec.encode("getUserName").unwrap(), 124_101_637);
//! ```
//!
//! The standard model ships inside the crate ([`mod@standard`]):
//! [`Codec::default`] and [`standard::standard`] are the standard codec.
//!
//! Non-standard models are allowed. A project can load any `NVM1` file with
//! [`Model::from_bytes`] and hand it to [`Codec::new`].

#![warn(missing_docs)]

use std::fmt;

mod bitio;
pub mod case;
mod codec;
mod huffman;
mod ladder;
pub mod model;
pub mod sha256;
pub mod standard;

pub use bitio::Bits;
pub use codec::Codec;
pub use model::Model;

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
    /// The bits name a tree with no leaves: a right cluster with no words.
    EmptyTree,
    /// The bits do not reach the STOP leaf within the word budget.
    DoesNotTerminate,
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
            Error::EmptyTree => write!(f, "an empty tree has no codewords"),
            Error::DoesNotTerminate => write!(f, "the identifier does not terminate"),
        }
    }
}

impl std::error::Error for Error {}

//! Bits, packed least-significant-bit first (`MODEL_FORMAT.md` §3).
//!
//! A codeword's *first* bit is the lowest bit of the first byte.  Reading past
//! the end yields zeros, which is what lets the all-zeros STOP codeword double
//! as the padding above the integer and so cost nothing.

/// Appends bits, LSB first within each byte.
#[derive(Clone, Debug, Default)]
pub struct BitWriter {
    bytes: Vec<u8>,
    bits: usize,
}

impl BitWriter {
    /// An empty writer.
    pub fn new() -> Self {
        BitWriter::default()
    }

    /// Append the low `width` bits of `value`, least significant first.
    pub fn put(&mut self, value: u32, width: u32) {
        for i in 0..width {
            if (value >> i) & 1 == 1 {
                let byte = self.bits / 8;
                while self.bytes.len() <= byte {
                    self.bytes.push(0);
                }
                self.bytes[byte] |= 1 << (self.bits % 8);
            }
            self.bits += 1;
        }
    }

    /// Drop the trailing zeros — they are the padding and the stop — and
    /// return the exact bit string.
    pub fn finish(mut self) -> Bits {
        while self.bits > 0 {
            let last = self.bits - 1;
            let byte = last / 8;
            if byte < self.bytes.len() && self.bytes[byte] & (1 << (last % 8)) != 0 {
                break;
            }
            self.bits -= 1;
        }
        self.bytes.truncate((self.bits + 7) / 8);
        Bits {
            bytes: self.bytes,
            len: self.bits,
        }
    }
}

/// Reads bits LSB first; past the end it returns zeros.
#[derive(Clone, Debug)]
pub struct BitReader<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> BitReader<'a> {
    /// A reader over `bytes`, positioned at bit 0.
    pub fn new(bytes: &'a [u8]) -> Self {
        BitReader { bytes, pos: 0 }
    }

    /// The position of the next bit.
    pub fn position(&self) -> usize {
        self.pos
    }

    /// Read `width` bits as an integer, first bit least significant.
    pub fn get(&mut self, width: u32) -> u32 {
        let mut value = 0;
        for i in 0..width {
            let byte = self.pos / 8;
            let bit = if byte < self.bytes.len() {
                (self.bytes[byte] >> (self.pos % 8)) & 1
            } else {
                0
            };
            value |= (bit as u32) << i;
            self.pos += 1;
        }
        value
    }

    /// Read one bit, most significant first — the order a codeword travels.
    pub fn get_bit(&mut self) -> u32 {
        self.get(1)
    }
}

/// A bit string of exact length: trailing zeros are already stripped.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Bits {
    bytes: Vec<u8>,
    len: usize,
}

impl Bits {
    /// The bits of a `u128`, low bit first, with no leading zeros.
    pub fn from_u128(value: u128) -> Self {
        let len = if value == 0 {
            0
        } else {
            (u128::BITS - value.leading_zeros()) as usize
        };
        Bits::from_bytes(&value.to_le_bytes(), len)
    }

    /// `len` bits taken from `bytes`, LSB first within each byte.
    ///
    /// # Panics
    ///
    /// Panics if `bytes` is shorter than `ceil(len / 8)`.
    pub fn from_bytes(bytes: &[u8], len: usize) -> Self {
        let nbytes = (len + 7) / 8;
        assert!(nbytes <= bytes.len(), "not enough bytes for {len} bits");
        let mut buf = bytes[..nbytes].to_vec();
        for i in len..nbytes * 8 {
            buf[i / 8] &= !(1 << (i % 8));
        }
        Bits {
            bytes: buf,
            len,
        }
    }

    /// The number of bits, trailing zeros included.
    pub fn len(&self) -> usize {
        self.len
    }

    /// True when the code occupies no bits at all (the empty identifier).
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// The bytes holding the bits, LSB first.
    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// The value as a `u128`, or `None` if a bit at index 128 or above is set.
    ///
    /// Being longer than 128 bits does not disqualify a code by itself: the
    /// trailing zeros of a codeword are not stored, so a long code whose top
    /// bits are zero still names an integer.  Only a set bit does not fit.
    pub fn to_u128(&self) -> Option<u128> {
        let mut value = 0u128;
        for i in 0..self.len {
            if (self.bytes[i / 8] >> (i % 8)) & 1 == 1 {
                if i >= 128 {
                    return None;
                }
                value |= 1 << i;
            }
        }
        Some(value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_u128_survives_the_round_trip() {
        for value in [0, 1, 27, 1 << 26, u128::MAX] {
            assert_eq!(Bits::from_u128(value).to_u128(), Some(value), "{value}");
        }
    }

    #[test]
    fn a_long_code_whose_top_bits_are_zero_still_fits() {
        // 130 bits: the widest u128, with two zero bits above it.
        let mut bytes = [0u8; 17];
        bytes[..16].copy_from_slice(&u128::MAX.to_le_bytes());
        let bits = Bits::from_bytes(&bytes, 130);
        assert_eq!(bits.len(), 130);
        assert_eq!(bits.to_u128(), Some(u128::MAX));
    }

    #[test]
    fn a_set_bit_above_the_128th_does_not_fit() {
        let mut bytes = [0u8; 17];
        bytes[16] = 1; // bit 128
        let bits = Bits::from_bytes(&bytes, 130);
        assert_eq!(bits.to_u128(), None);
    }
}

//! The rule ladder and the variable-width integer (`MODEL_FORMAT.md` §4).
//!
//! Both are *static*: the decoder derives every interval edge from `n` alone,
//! so nothing is stored for the code.

use crate::bitio::{BitReader, BitWriter};

/// Index bits; the ladder has `2 ** LADDER_B` intervals.
pub const LADDER_B: u32 = 3;

/// Bits needed to hold the values `0 .. n - 1`.
pub fn ceil_log2(n: u32) -> u32 {
    if n <= 1 {
        0
    } else {
        32 - (n - 1).leading_zeros()
    }
}

/// Append `n` as a base-128 little-endian varint.
pub fn put_varint(n: u64, out: &mut Vec<u8>) {
    let mut n = n;
    loop {
        let b = (n & 0x7F) as u8;
        n >>= 7;
        out.push(b | if n != 0 { 0x80 } else { 0 });
        if n == 0 {
            return;
        }
    }
}

/// Read a varint at `*pos`, advancing the position.
pub fn read_varint(buf: &[u8], pos: &mut usize) -> Result<u64, crate::Error> {
    let mut value = 0u64;
    let mut shift = 0;
    loop {
        let b = *buf
            .get(*pos)
            .ok_or(crate::Error::Truncated("the varint runs past the end"))?;
        *pos += 1;
        value |= ((b & 0x7F) as u64) << shift;
        shift += 7;
        if b & 0x80 == 0 {
            return Ok(value);
        }
        if shift > 63 {
            return Err(crate::Error::Model("a varint overflows 64 bits"));
        }
    }
}

/// `(l, s)` for a variable-width integer over `[0, n)`.
fn variable_widths(n: u32) -> (u32, u32) {
    let l = 31 - n.leading_zeros(); // n >= 2 here
    (l, n - (1 << l))
}

fn variable_put(bw: &mut BitWriter, x: u32, n: u32) {
    if n <= 1 {
        return;
    }
    let (l, s) = variable_widths(n);
    if x < (1 << l) {
        bw.put(x, l);
        if x >= (1 << l) - s {
            bw.put(0, 1);
        }
    } else {
        bw.put(x - s, l);
        bw.put(1, 1);
    }
}

fn variable_get(br: &mut BitReader<'_>, n: u32) -> u32 {
    if n <= 1 {
        return 0;
    }
    let (l, s) = variable_widths(n);
    let v = br.get(l);
    if v < (1 << l) - s {
        v
    } else if br.get(1) == 0 {
        v
    } else {
        v + s
    }
}

/// The nine interval edges of the base-2 geometric ladder over `[0, n)`.
///
/// `e_i = n (2**i - 1) / (2**B - 1)` in integers, with `B = 2 ** LADDER_B`, so
/// the decoder computes them from `n` with no stored table.
pub fn ladder_edges(n: u32) -> [u32; 9] {
    let den = (1u64 << (1 << LADDER_B)) - 1;
    let mut edges = [0u32; 9];
    for (i, edge) in edges.iter_mut().enumerate() {
        *edge = ((n as u64) * ((1u64 << i) - 1) / den) as u32;
    }
    edges
}

/// The interval that holds `x`: the last edge at or below it.
fn ladder_interval(edges: &[u32; 9], x: u32) -> u32 {
    let mut found = 0;
    for (i, &edge) in edges.iter().enumerate().take(8) {
        if x >= edge {
            found = i as u32;
        }
    }
    found
}

fn interval_width(edges: &[u32; 9], index: u32) -> u32 {
    let width = edges[index as usize + 1] - edges[index as usize];
    width.max(1)
}

/// Code `x` in `[0, n)`.
pub fn ladder_put(bw: &mut BitWriter, x: u32, n: u32) {
    let edges = ladder_edges(n);
    let i = ladder_interval(&edges, x);
    bw.put(i, LADDER_B);
    let width = interval_width(&edges, i);
    let offset = x.saturating_sub(edges[i as usize]).min(width - 1);
    variable_put(bw, offset, width);
}

/// Read one codeword of the ladder over `[0, n)`.
pub fn ladder_get(br: &mut BitReader<'_>, n: u32) -> u32 {
    let edges = ladder_edges(n);
    let i = br.get(LADDER_B);
    let width = interval_width(&edges, i);
    edges[i as usize] + variable_get(br, width)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn edges_and_intervals() {
        let edges = ladder_edges(8_191);
        assert_eq!(edges[0], 0);
        assert_eq!(edges[8], 8_191);
        assert!(edges.windows(2).all(|w| w[0] <= w[1]));
        for x in [0u32, 1, 31, 32, 1_000, 4_096, 8_190] {
            let i = ladder_interval(&edges, x);
            assert!(edges[i as usize] <= x && x < edges[i as usize + 1]);
        }
    }

    #[test]
    fn round_trip() {
        for n in [2u32, 9, 100, 8_191] {
            for x in [0, 1, n / 3, n - 2, n - 1] {
                let mut w = BitWriter::new();
                ladder_put(&mut w, x, n);
                let bits = w.finish();
                assert_eq!(ladder_get(&mut bits.reader(), n), x);
            }
        }
    }

    #[test]
    fn varints() {
        for n in [0u64, 1, 127, 128, 8_191, u32::MAX as u64] {
            let mut buf = Vec::new();
            put_varint(n, &mut buf);
            let mut pos = 0;
            assert_eq!(read_varint(&buf, &mut pos).unwrap(), n);
            assert_eq!(pos, buf.len());
        }
    }
}

//! Canonical Huffman trees, as `MODEL_FORMAT.md` §2 defines them.
//!
//! The model file stores one depth per leaf; the codeword of each leaf and the
//! decision tree the decoder walks are both derived from those depths, here and
//! nowhere else.  `model` sees only the public methods below.

use crate::bitio::{BitReader, BitWriter};
use crate::Error;

/// One depth of a canonical tree, as the decoder sees it.
///
/// Canonical codes place the leaves of one depth in a contiguous range of
/// values, so decoding is a range test per depth rather than a table lookup.
#[derive(Clone, Copy, Debug)]
struct Level {
    /// The smallest value that is a leaf at this depth.
    first: u32,
    /// How many leaves there are at this depth.
    count: u32,
    /// Where those leaves start in [`Tree::book`].
    index: u32,
}

/// A canonical Huffman tree: one codeword per leaf position.
///
/// `MODEL_FORMAT.md` §2 fixes the assignment: code 0 goes to the first leaf at
/// the maximum depth, codes ascend within a depth, and the space is filled from
/// the top down.  The deepest leaves therefore take the lowest values, which is
/// what puts the all-zeros path on position 0 — in a top tree the STOP leaf,
/// and in a code the integer's padding.
///
/// `levels` is the source of truth.  It is gathered from the depths in one walk
/// up from the deepest level, and the two views the codec needs are read off it:
///
/// * `codes[position] = (value, length)`, the encoder's view;
/// * [`book`](Tree::book), the decoder's: the positions in canonical allocation
///   order, deepest depth first and ascending within a depth.
///
/// A tree with no leaves is a tree like any other: it has no codewords, so
/// [`read`](Tree::read) fails and every [`write`](Tree::write) names a missing
/// position.
#[derive(Clone, Debug)]
pub struct Tree {
    codes: Vec<(u32, u32)>,
    book: Vec<u32>,
    levels: Vec<Level>,
}

impl Tree {
    /// Build the tree with one depth per leaf position, in stored order.
    ///
    /// A position's codeword is `depths[position]` bits long, and the depths
    /// must fit the space: the Kraft sum may not exceed 1.  It is exactly 1 for
    /// a complete tree, which has a leaf at the end of every path; a bottom
    /// tree may be incomplete, and then some bit strings are nobody's codeword.
    pub fn from_depths(depths: &[u32]) -> Tree {
        if depths.is_empty() {
            return Tree {
                codes: Vec::new(),
                book: Vec::new(),
                levels: Vec::new(),
            };
        }
        let maxd = *depths.iter().max().expect("a non-empty depth table") as usize;
        let mut levels = vec![
            Level {
                first: 0,
                count: 0,
                index: 0,
            };
            maxd + 1
        ];
        for &d in depths {
            levels[d as usize].count += 1;
        }
        // One walk up from the deepest level fixes both where each depth's
        // leaves start and where they sit in the book.  The deepest leaves take
        // values 0, 1, …, so each depth up starts where the deeper block ends,
        // halved and rounded up: the children of value v are 2v and 2v+1.  The
        // rounding is exact for a complete tree; for an incomplete one it
        // leaves a gap between the blocks, and the reader treats a value in
        // that gap as no codeword at all.
        let (mut first, mut at) = (0u32, 0u32);
        for level in levels.iter_mut().rev() {
            level.first = first;
            first = (first + level.count + 1) / 2;
            level.index = at;
            at += level.count;
        }
        // `model` checks Kraft's sum on the file's table before building, and
        // this walk is the decoder's view of the same requirement: a tree that
        // fills its space comes back to 1 above the root.  The walk alone is a
        // tripwire, not the check — truncating division still lands on 1 for a
        // table that is only slightly over-full.
        assert_eq!(first, 1, "a depth table over-fills the code space");
        // The encoder's view: within a depth the codes ascend with position,
        // so a leaf's value is its depth's `first` plus how many leaves of that
        // depth come before it.
        let mut next: Vec<u32> = levels.iter().map(|level| level.first).collect();
        let mut codes = vec![(0u32, 0u32); depths.len()];
        for (position, &d) in depths.iter().enumerate() {
            let value = &mut next[d as usize];
            codes[position] = (*value, d);
            *value += 1;
        }
        // The book: the same positions in canonical allocation order, i.e. by
        // ascending depth counting down, and ascending within a depth.
        let mut next: Vec<u32> = levels.iter().map(|level| level.index).collect();
        let mut book = vec![0u32; depths.len()];
        for (position, &d) in depths.iter().enumerate() {
            let at = &mut next[d as usize];
            book[*at as usize] = position as u32;
            *at += 1;
        }
        Tree {
            codes,
            book,
            levels,
        }
    }

    /// The number of leaves: the number of codewords.
    pub fn num_leaves(&self) -> u32 {
        self.codes.len() as u32
    }

    /// Append the codeword of `position`, most significant bit first.
    pub fn write(&self, writer: &mut BitWriter, position: u32) -> Result<(), Error> {
        let &(value, length) = self
            .codes
            .get(position as usize)
            .ok_or(Error::Model("a codeword position is outside the table"))?;
        for shift in (0..length).rev() {
            writer.put((value >> shift) & 1, 1);
        }
        Ok(())
    }

    /// Read one codeword and return the leaf position.
    ///
    /// A codeword is a prefix of the stream, so the depths are tried from 0
    /// upwards: if the bits read so far are one of this depth's leaves, that
    /// is the answer; if they are below the depth's leaves, the deeper leaves
    /// are all down there and one more bit is read; if they are beyond them,
    /// no leaf is left and the bits are not a codeword at all.
    ///
    /// Depth 0 is a tree with one leaf — the empty codeword — so it is found
    /// before any bit is read.
    pub fn read(&self, reader: &mut BitReader<'_>) -> Result<u32, Error> {
        if self.book.is_empty() {
            return Err(Error::EmptyTree);
        }
        let mut value = 0;
        for level in &self.levels {
            if value < level.first {
                value = (value << 1) | reader.get_bit();
                continue;
            }
            let offset = value - level.first;
            if offset < level.count {
                return Ok(self.book[(level.index + offset) as usize]);
            }
            return Err(Error::Model("the bits are not a codeword of this tree"));
        }
        Err(Error::Model("no codeword within the tree's maximum depth"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A reader over the bits of `bits`, first bit leftmost in the string.
    fn bits_of(bits: &str) -> Vec<u8> {
        let mut bytes = vec![0u8; (bits.len() + 7) / 8];
        for (i, b) in bits.bytes().enumerate() {
            assert!(b == b'0' || b == b'1', "not a bit string: {bits}");
            if b == b'1' {
                bytes[i / 8] |= 1 << (i % 8);
            }
        }
        bytes
    }

    /// The leaf `bits` names, and how many bits of it the reader took.
    fn leaf_of(tree: &Tree, bits: &str) -> (Result<u32, Error>, usize) {
        let bytes = bits_of(bits);
        let mut reader = BitReader::new(&bytes);
        let leaf = tree.read(&mut reader);
        (leaf, reader.position())
    }

    /// Every leaf of `depths` must survive a write/read round trip, and every
    /// bit string of a complete tree must decode: a complete tree has no holes.
    fn round_trip_depths(depths: &[u32]) {
        let tree = Tree::from_depths(depths);
        assert_eq!(tree.num_leaves(), depths.len() as u32);
        for position in 0..depths.len() as u32 {
            let mut writer = BitWriter::new();
            tree.write(&mut writer, position).expect("a leaf");
            // `finish` strips the trailing zeros, so the bytes can be shorter
            // than the codeword; the reader pads with zeros, and the position
            // it ends at is the codeword's true length.
            let bits = writer.finish();
            assert!(bits.len() <= depths[position as usize] as usize);
            let mut reader = BitReader::new(bits.as_bytes());
            assert_eq!(
                tree.read(&mut reader),
                Ok(position),
                "depths {depths:?}, position {position}"
            );
            assert_eq!(
                reader.position(),
                depths[position as usize] as usize,
                "depths {depths:?}, position {position}"
            );
        }
        let maxd = *depths.iter().max().unwrap();
        let kraft: u32 = depths.iter().map(|&d| 1u32 << (maxd - d)).sum();
        if kraft == 1 << maxd && maxd <= 10 {
            let width = maxd as usize;
            for value in 0..1u32 << maxd {
                let mut bytes = vec![0u8; (width + 7) / 8];
                for i in 0..width {
                    let bit = (value >> (width - 1 - i)) & 1;
                    bytes[i / 8] |= (bit as u8) << (i % 8);
                }
                let mut reader = BitReader::new(&bytes);
                tree.read(&mut reader).unwrap_or_else(|err| {
                    panic!("depths {depths:?}, bits {value:0width$b}: {err}")
                });
            }
        }
    }

    #[test]
    fn a_single_leaf_codes_in_no_bits() {
        let tree = Tree::from_depths(&[0]);
        assert_eq!(tree.num_leaves(), 1);
        let mut writer = BitWriter::new();
        tree.write(&mut writer, 0).expect("the only leaf");
        assert!(writer.finish().is_empty());
        let mut reader = BitReader::new(&[]);
        assert_eq!(tree.read(&mut reader), Ok(0));
        assert_eq!(reader.position(), 0);
    }

    #[test]
    fn an_empty_tree_has_no_codewords() {
        let tree = Tree::from_depths(&[]);
        assert_eq!(tree.num_leaves(), 0);
        assert!(matches!(
            tree.read(&mut BitReader::new(&[0xff])),
            Err(Error::EmptyTree)
        ));
        let mut writer = BitWriter::new();
        assert!(tree.write(&mut writer, 0).is_err());
        assert!(writer.finish().is_empty());
    }

    #[test]
    fn the_deepest_leaves_take_the_lowest_values() {
        // Depths 1, 2, 2 make a complete tree: the depth-2 leaves are values 0
        // and 1, the depth-1 leaf the value above them.
        let tree = Tree::from_depths(&[1, 2, 2]);
        assert_eq!(leaf_of(&tree, "1"), (Ok(0), 1));
        assert_eq!(leaf_of(&tree, "00"), (Ok(1), 2));
        assert_eq!(leaf_of(&tree, "01"), (Ok(2), 2));
        // The book is in allocation order: deepest first, ascending within a
        // depth.
        assert_eq!(tree.book, [1, 2, 0]);
    }

    #[test]
    fn the_codes_of_every_depth_line_up() {
        // One leaf at each depth 1 to 4 and one more at the bottom: 2**-d sums
        // to exactly 1, so each depth's block ends where the next begins.
        let tree = Tree::from_depths(&[1, 2, 3, 4, 4]);
        assert_eq!(leaf_of(&tree, "1"), (Ok(0), 1));
        assert_eq!(leaf_of(&tree, "01"), (Ok(1), 2));
        assert_eq!(leaf_of(&tree, "001"), (Ok(2), 3));
        assert_eq!(leaf_of(&tree, "0000"), (Ok(3), 4));
        assert_eq!(leaf_of(&tree, "0001"), (Ok(4), 4));
        assert_eq!(tree.book, [3, 4, 2, 1, 0]);
    }

    #[test]
    fn the_range_decoder_finds_every_leaf() {
        // Complete trees, built by splitting leaves, and the incomplete ones a
        // truncated build can leave behind.  The second kind matters: its
        // Kraft sum is below 1, so the depth boundaries cannot be recovered by
        // doubling alone, and the stored `first` has to carry the rounding.
        let mut seed = 0x9e37_79b9_7f4a_7c15u64;
        let mut roll = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        for _ in 0..300 {
            let mut depths = vec![0u32];
            for _ in 0..roll() % 24 {
                let at = (roll() as usize) % depths.len();
                if depths[at] < 20 {
                    depths[at] += 1;
                    let deeper = depths[at];
                    depths.push(deeper);
                }
            }
            if depths.len() > 1 && roll() % 4 == 0 {
                depths.pop(); // incomplete: allowed for a bottom tree
            }
            round_trip_depths(&depths);
        }
        round_trip_depths(&[0]);
        round_trip_depths(&[2, 2, 2]);
        round_trip_depths(&[2, 1, 2]);
    }

    #[test]
    fn a_hole_in_an_incomplete_tree_is_not_a_leaf() {
        // Depths 2,2,2 have values 0, 1 and 2; value 3 is unassigned.
        let tree = Tree::from_depths(&[2, 2, 2]);
        let mut reader = BitReader::new(&[0b11]);
        assert!(matches!(
            tree.read(&mut reader),
            Err(Error::Model("the bits are not a codeword of this tree"))
        ));
    }

    #[test]
    #[should_panic(expected = "over-fills the code space")]
    fn a_grossly_over_full_table_is_a_bug() {
        // Five leaves at depth 1 need 5/2 of the space.  `model` refuses such
        // a table before it gets here; the builder still notices.
        Tree::from_depths(&[1, 1, 1, 1, 1]);
    }
}

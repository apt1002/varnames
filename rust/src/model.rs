//! Reading the `NVM1` model file of `MODEL_FORMAT.md`.
//!
//! A model is a word list (a pair-merge dictionary), one depth table for the
//! word trees and one for the cluster trees, plus the membership map.
//! Everything else — codewords, leaf lists, the cluster of a word — is derived
//! here, once, at load time.
//!
//! The reader is strict: every invariant the format states is checked, so a
//! corrupt or truncated file fails at load rather than at decode.

use std::collections::HashMap;

use crate::bitio::{BitReader, BitWriter};
use crate::ladder::{ceil_log2, ladder_get, read_varint};
use crate::Error;

/// The four magic bytes every model file starts with.
pub const MAGIC: [u8; 4] = *b"NVM1";
/// The depth field is always four bits (`MODEL_FORMAT.md` §3).
pub const DEPTH_BITS: u32 = 4;

/// One canonical Huffman tree: `codes[position] = (value, length)`.
///
/// Position is the leaf's place in the stored depth sequence: the symbol id for
/// a word tree, and `0 = STOP, 1 + j = right cluster j` for a top tree.
#[derive(Clone, Debug)]
pub struct Tree {
    codes: Vec<(u32, u32)>,
    book: HashMap<(u32, u32), u32>,
    max_len: u32,
    single: Option<u32>,
}

impl Tree {
    /// Build a tree from its leaf depths, in stored order.
    pub fn new(depths: &[u32]) -> Result<Tree, Error> {
        let codes = canonical_codes(depths);
        let mut book = HashMap::with_capacity(codes.len());
        for (pos, &(value, length)) in codes.iter().enumerate() {
            book.insert((length, value), pos as u32);
        }
        let max_len = depths.iter().copied().max().unwrap_or(0);
        let single = if depths.len() == 1 { Some(0) } else { None };
        Ok(Tree {
            codes,
            book,
            max_len,
            single,
        })
    }

    /// The number of leaves.
    pub fn len(&self) -> usize {
        self.codes.len()
    }

    /// Whether the tree has no leaves.
    pub fn is_empty(&self) -> bool {
        self.codes.is_empty()
    }

    /// The longest codeword, in bits.
    pub fn max_len(&self) -> u32 {
        self.max_len
    }

    /// Append the codeword of `position`, most significant bit first.
    pub fn write(&self, writer: &mut BitWriter, position: usize) -> Result<(), Error> {
        let &(value, length) = self
            .codes
            .get(position)
            .ok_or(Error::Model("a codeword position is outside the table"))?;
        for shift in (0..length).rev() {
            writer.put((value >> shift) & 1, 1);
        }
        Ok(())
    }

    /// Read one codeword and return the leaf position.
    pub fn read(&self, reader: &mut BitReader<'_>) -> Result<u32, Error> {
        if let Some(pos) = self.single {
            return Ok(pos); // a one-leaf tree codes in zero bits
        }
        let mut value = 0;
        for length in 1..=self.max_len {
            value = (value << 1) | reader.get_bit();
            if let Some(&pos) = self.book.get(&(length, value)) {
                return Ok(pos);
            }
        }
        Err(Error::Model("no codeword within the tree's maximum depth"))
    }
}

/// `MODEL_FORMAT.md` §2: code 0 is the first leaf at the maximum depth.
///
/// Codes ascend within a depth and the space is filled from the top down, so
/// the deepest leaves take the low values — which is what puts the all-zeros
/// path on leaf 0 of a top tree, the STOP leaf.
pub fn canonical_codes(depths: &[u32]) -> Vec<(u32, u32)> {
    let n = depths.len();
    if n == 0 {
        return Vec::new();
    }
    let maxd = *depths.iter().max().unwrap();
    let mut codes = vec![(0u32, 0u32); n];
    let mut next: u64 = 0;
    for length in (0..=maxd).rev() {
        let block = 1u64 << (maxd - length);
        let start = (next + block - 1) / block;
        let mut step = 0u64;
        for (pos, &d) in depths.iter().enumerate() {
            if d == length {
                codes[pos] = ((start + step) as u32, length);
                step += 1;
            }
        }
        next = (start + step) * block;
    }
    codes
}

/// Add back the per-tree offset, which is recovered from the Kraft sum.
///
/// A complete tree has `sum 2**-d = 1`; with `d = o + delta` that is
/// `2**o = sum 2**-delta`, so `o` is the (whole) exponent of the sum.
fn depths_from_offsets(deltas: &[u32]) -> Result<Vec<u32>, Error> {
    if deltas.is_empty() {
        return Ok(Vec::new());
    }
    let mut total: u64 = 0;
    for &d in deltas {
        total += 1u64 << (15 - d);
    }
    let offset = total.trailing_zeros() as i32 - 15;
    if total != 1u64 << (offset + 15) {
        return Err(Error::Model("a depth table's Kraft sum is not a power of two"));
    }
    deltas
        .iter()
        .map(|&d| {
            let depth = d as i32 + offset;
            if depth < 0 || depth > 31 {
                Err(Error::Model("a depth is outside 0..=31"))
            } else {
                Ok(depth as u32)
            }
        })
        .collect()
}

/// A loaded model: the tables plus every derived view the codec needs.
#[derive(Clone, Debug)]
pub struct Model {
    alphabet: Vec<char>,
    rules: Vec<(u32, u32)>,
    memberships: Vec<u32>,
    bottom_depths: Vec<u32>,
    top_depths: Vec<Vec<u32>>,
    v: u32,
    k: u32,
    q: u32,
    nchars: u32,
    char_id: HashMap<char, u32>,
    left: Vec<u32>,
    cluster_ids: Vec<Vec<u32>>,
    pos_in_cluster: Vec<u32>,
    bottom_trees: Vec<Option<Tree>>,
    top_trees: Vec<Tree>,
    plan: HashMap<(u32, u32), (u32, u32)>,
}

impl Model {
    fn build(
        alphabet: Vec<char>,
        rules: Vec<(u32, u32)>,
        memberships: Vec<u32>,
        bottom_depths: Vec<u32>,
        top_depths: Vec<Vec<u32>>,
        v: u32,
        k: u32,
        q: u32,
    ) -> Result<Model, Error> {
        let nchars = alphabet.len() as u32;
        let kq = k * q;
        if v != nchars + rules.len() as u32 {
            return Err(Error::Model("v is not the alphabet plus the rule list"));
        }
        if memberships.len() as u32 != v {
            return Err(Error::Model("the membership map does not cover v"));
        }
        if bottom_depths.len() as u32 != v {
            return Err(Error::Model("the word-depth table does not cover v"));
        }
        if top_depths.len() as u32 != k {
            return Err(Error::Model("the cluster-depth table does not cover k"));
        }
        for depths in top_depths.iter() {
            if depths.len() as u32 != kq + 1 {
                return Err(Error::Model(
                    "a cluster tree does not have kq + 1 leaves",
                ));
            }
            if depths.len() > 1 && depths[0] != *depths.iter().max().unwrap() {
                return Err(Error::Model(
                    "a cluster tree's STOP leaf is not the deepest",
                ));
            }
            require_complete(depths)?;
        }

        let char_id = alphabet
            .iter()
            .enumerate()
            .map(|(i, &c)| (c, i as u32))
            .collect();

        let mut cluster_ids: Vec<Vec<u32>> = vec![Vec::new(); kq as usize];
        for (symbol, &cluster) in memberships.iter().enumerate() {
            if cluster >= kq {
                return Err(Error::Model(
                    "a membership names a cluster that does not exist",
                ));
            }
            cluster_ids[cluster as usize].push(symbol as u32);
        }
        let mut pos_in_cluster = vec![0u32; v as usize];
        let mut bottom_trees: Vec<Option<Tree>> = vec![None; kq as usize];
        for cluster in 0..kq {
            let ids = &cluster_ids[cluster as usize];
            let depths: Vec<u32> = ids
                .iter()
                .map(|&s| bottom_depths[s as usize])
                .collect();
            if depths.is_empty() {
                continue;
            }
            require_kraft(&depths)?;
            for (position, &symbol) in ids.iter().enumerate() {
                pos_in_cluster[symbol as usize] = position as u32;
            }
            bottom_trees[cluster as usize] = Some(Tree::new(&depths)?);
        }

        let top_trees: Vec<Tree> = top_depths
            .iter()
            .map(|depths| Tree::new(depths))
            .collect::<Result<_, _>>()?;

        let left: Vec<u32> = memberships.iter().map(|&m| m / q).collect();
        let mut plan = HashMap::with_capacity(rules.len());
        for (rank, &(a, b)) in rules.iter().enumerate() {
            plan.insert((a, b), (rank as u32, nchars + rank as u32));
        }

        Ok(Model {
            alphabet,
            rules,
            memberships,
            bottom_depths,
            top_depths,
            v,
            k,
            q,
            nchars,
            char_id,
            left,
            cluster_ids,
            pos_in_cluster,
            bottom_trees,
            top_trees,
            plan,
        })
    }

    /// Parse a model file.
    pub fn from_bytes(buf: &[u8]) -> Result<Model, Error> {
        if buf.len() < 4 || buf[..4] != MAGIC {
            return Err(Error::BadMagic);
        }
        let mut pos = 4;
        let v = read_varint(buf, &mut pos)?;
        let k = read_varint(buf, &mut pos)?;
        let q = read_varint(buf, &mut pos)?;
        let nchars = read_varint(buf, &mut pos)?;
        let rules_len = read_varint(buf, &mut pos)?;
        if v <= nchars || v > u32::MAX as u64 || k == 0 || q == 0 || k > 1 << 16 {
            return Err(Error::Model("the header is inconsistent"));
        }
        let (v, k, q, nchars, rules_len) =
            (v as u32, k as u32, q as u32, nchars as u32, rules_len as usize);
        let end = pos
            .checked_add(rules_len)
            .filter(|&end| end <= buf.len())
            .ok_or(Error::Truncated("the rule table runs past the end"))?;
        let kq = k * q;

        let mut reader = BitReader::new(&buf[pos..end]);
        let mut rules = Vec::with_capacity((v - nchars) as usize);
        for i in 0..(v - nchars) {
            let n = nchars + i;
            let a = ladder_get(&mut reader, n);
            let b = ladder_get(&mut reader, n);
            if a >= n || b >= n {
                return Err(Error::Model("a rule names a child that does not exist"));
            }
            rules.push((a, b));
        }
        pos = end;

        let stop = pos
            .checked_add(nchars as usize)
            .filter(|&stop| stop <= buf.len())
            .ok_or(Error::Truncated("truncated alphabet"))?;
        if buf[pos..stop].iter().any(|&b| !b.is_ascii()) {
            return Err(Error::Model("the alphabet is not ASCII"));
        }
        let alphabet: Vec<char> = buf[pos..stop].iter().map(|&b| b as char).collect();
        pos = stop;

        let width = ceil_log2(kq);
        let nbytes = ((v as u64 * width as u64 + 7) / 8) as usize;
        let end = pos
            .checked_add(nbytes)
            .filter(|&end| end <= buf.len())
            .ok_or(Error::Truncated("truncated membership map"))?;
        let mut reader = BitReader::new(&buf[pos..end]);
        let memberships: Vec<u32> = (0..v).map(|_| reader.get(width)).collect();
        if memberships.iter().any(|&m| m >= kq) {
            return Err(Error::Model(
                "a membership names a cluster that does not exist",
            ));
        }
        pos = end;

        let nbytes = ((v as u64 * DEPTH_BITS as u64 + 7) / 8) as usize;
        let end = pos
            .checked_add(nbytes)
            .filter(|&end| end <= buf.len())
            .ok_or(Error::Truncated("truncated word-depth table"))?;
        let mut reader = BitReader::new(&buf[pos..end]);
        let mut bottom_depths = vec![0u32; v as usize];
        for cluster in 0..kq {
            let ids: Vec<usize> = memberships
                .iter()
                .enumerate()
                .filter(|&(_, &m)| m == cluster)
                .map(|(i, _)| i)
                .collect();
            let deltas: Vec<u32> = ids.iter().map(|_| reader.get(DEPTH_BITS)).collect();
            for (&id, depth) in ids.iter().zip(depths_from_offsets(&deltas)?) {
                bottom_depths[id] = depth;
            }
        }
        pos = end;

        let nbytes = ((k as u64 * (kq as u64 + 1) * DEPTH_BITS as u64 + 7) / 8) as usize;
        let end = pos
            .checked_add(nbytes)
            .filter(|&end| end <= buf.len())
            .ok_or(Error::Truncated("truncated cluster-depth table"))?;
        let mut reader = BitReader::new(&buf[pos..end]);
        let mut top_depths = Vec::with_capacity(k as usize);
        for _ in 0..k {
            let deltas: Vec<u32> = (0..=kq).map(|_| reader.get(DEPTH_BITS)).collect();
            top_depths.push(depths_from_offsets(&deltas)?);
        }
        pos = end;

        if pos != buf.len() {
            return Err(Error::Model("trailing bytes after the model"));
        }
        Model::build(
            alphabet,
            rules,
            memberships,
            bottom_depths,
            top_depths,
            v,
            k,
            q,
        )
    }

    // ------------------------------------------------------------- accessors

    /// The vocabulary size: the alphabet plus the rule list.
    pub fn v(&self) -> u32 {
        self.v
    }
    /// The number of left clusters.
    pub fn k(&self) -> u32 {
        self.k
    }
    /// The number of right clusters per left cluster.
    pub fn q(&self) -> u32 {
        self.q
    }
    /// The alphabet size; word ids start here and the STOP id is `nchars`.
    pub fn nchars(&self) -> u32 {
        self.nchars
    }
    /// The pair-merge rule list, in rank order.
    pub fn rules(&self) -> &[(u32, u32)] {
        &self.rules
    }
    /// The characters, in symbol-id order.
    pub fn alphabet(&self) -> &[char] {
        &self.alphabet
    }
    /// The right cluster of every symbol.
    pub fn memberships(&self) -> &[u32] {
        &self.memberships
    }
    /// The stored word-tree depth of every symbol.
    pub fn bottom_depths(&self) -> &[u32] {
        &self.bottom_depths
    }
    /// The stored depths of the cluster trees, one per left cluster.
    pub fn top_depths(&self) -> &[Vec<u32>] {
        &self.top_depths
    }
    /// The left cluster a symbol starts in.
    pub fn left_cluster(&self, symbol: u32) -> u32 {
        self.left[symbol as usize]
    }
    /// The symbol at a position in a right cluster.
    pub fn symbol_of(&self, cluster: u32, position: u32) -> Result<u32, Error> {
        self.cluster_ids
            .get(cluster as usize)
            .and_then(|ids| ids.get(position as usize))
            .copied()
            .ok_or(Error::Model("a word position is outside its cluster"))
    }
    /// The position of a symbol in its right cluster.
    pub fn position_of(&self, symbol: u32) -> Result<u32, Error> {
        self.pos_in_cluster
            .get(symbol as usize)
            .copied()
            .ok_or(Error::Model("a symbol is outside the model"))
    }
    /// The right cluster a symbol belongs to.
    pub fn cluster_of(&self, symbol: u32) -> Result<u32, Error> {
        self.memberships
            .get(symbol as usize)
            .copied()
            .ok_or(Error::Model("a symbol is outside the model"))
    }
    /// A character's symbol id, if the model has it.
    pub fn char_id(&self, c: char) -> Option<u32> {
        self.char_id.get(&c).copied()
    }
    /// The tokeniser plan: child pair -> (rank, new id).
    pub fn plan(&self) -> &HashMap<(u32, u32), (u32, u32)> {
        &self.plan
    }
    /// The cluster tree of a left cluster.
    pub fn top_tree(&self, left: u32) -> &Tree {
        &self.top_trees[left as usize]
    }
    /// The word tree of a right cluster, if it has words.
    pub fn bottom_tree(&self, cluster: u32) -> Option<&Tree> {
        self.bottom_trees[cluster as usize].as_ref()
    }

    /// One line describing the model, for logs and the CLI.
    pub fn info(&self) -> String {
        format!(
            "V={} k={} q={} alphabet={} rules={} kq={}",
            self.v,
            self.k,
            self.q,
            self.nchars,
            self.rules.len(),
            self.k * self.q
        )
    }
}

fn require_complete(depths: &[u32]) -> Result<(), Error> {
    if depths.is_empty() {
        return Ok(());
    }
    let maxd = *depths.iter().max().unwrap();
    if maxd > 30 {
        return Err(Error::Model("a depth is too large to check"));
    }
    let total: u64 = depths.iter().map(|&d| 1u64 << (maxd - d)).sum();
    if total != 1u64 << maxd {
        return Err(Error::Model("a depth table is not a complete tree"));
    }
    Ok(())
}

fn require_kraft(depths: &[u32]) -> Result<(), Error> {
    if depths.is_empty() {
        return Ok(());
    }
    let maxd = *depths.iter().max().unwrap();
    if maxd > 30 {
        return Err(Error::Model("a depth is too large to check"));
    }
    let total: u64 = depths.iter().map(|&d| 1u64 << (maxd - d)).sum();
    if total > 1u64 << maxd {
        return Err(Error::Model("a word tree over-fills the code space"));
    }
    Ok(())
}

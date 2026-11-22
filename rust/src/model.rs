//! Reading the `NVM1` model file of `MODEL_FORMAT.md`.
//!
//! A model is a word list (a pair-merge dictionary), one depth table for the
//! word trees and one for the cluster trees, plus the membership map.
//! Everything else — leaf lists, the cluster of a word, which tree codes what —
//! is derived here, once, at load time; the depth tables become codewords in
//! the crate's `huffman` module.
//!
//! Every index has its own type — [`Char`], [`Rule`], [`Word`], [`Left`],
//! [`Right`], [`RightLeaf`], [`LeftLeaf`] — so a right cluster cannot be passed
//! where a left cluster is meant.  The accessors below validate what they are
//! given and return the derived information; the tables themselves stay
//! private.
//!
//! The reader is strict: every invariant the format states is checked, so a
//! corrupt or truncated file fails at load rather than at decode.

use std::collections::{HashMap, HashSet};

use crate::bitio::{BitReader, BitWriter};
use crate::huffman::Tree;
use crate::ladder::{ceil_log2, ladder_get, read_varint};
use crate::Error;

/// The four magic bytes every model file starts with.
pub const MAGIC: [u8; 4] = *b"NVM1";
/// The depth field is always four bits (`MODEL_FORMAT.md` §3).
pub const DEPTH_BITS: u32 = 4;

// ------------------------------------------------------------ index types
//
// The tables are indexed by small integers of several different kinds, and a
// bare `u32` cannot say which kind it is.  These one-field structs can.  They
// cost nothing at run time (`#[repr(transparent)]`), and every `Model` method
// that takes one checks it, so an index invented by hand is an error rather
// than a wrong answer.

/// An index into the alphabet: `0 <= c < num_chars()`.
///
/// Characters are the first words of the model — `STANDARD.md` numbers them
/// `0 … C-1` — so a `Char` is also a [`Word`] of the same value
/// ([`Char::word`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(transparent)]
pub struct Char(pub u32);

/// An index into the rule list: `0 <= r < num_rules()`.
///
/// The index is also the rule's **rank** in `STANDARD.md` §5, the order in
/// which the tokeniser applies rules; the word the rule defines is
/// `num_chars() + rule` ([`Model::word_of_rule`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
#[repr(transparent)]
pub struct Rule(pub u32);

/// A word id: `0 <= w < num_words()`, which is `V` in `STANDARD.md`.
///
/// Ids below `num_chars()` are characters; the rest are the words the rules
/// define.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(transparent)]
pub struct Word(pub u32);

/// A left cluster: `0 <= l < num_lefts()`, which is `k` in `STANDARD.md`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(transparent)]
pub struct Left(pub u32);

/// A right cluster: `0 <= r < num_rights()`, which is `kq` in `STANDARD.md`.
///
/// The right clusters `l·q … l·q + q - 1` belong to left cluster `l`, where
/// `q` is [`Model::num_rights_per_left`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(transparent)]
pub struct Right(pub u32);

/// A word's position in its right cluster's word list, from 0 to the number of
/// words in the cluster minus one.
///
/// The list is in ascending word id (`MODEL_FORMAT.md` §2), and the tree that
/// codes a position is [`Model::bottom_tree`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(transparent)]
pub struct RightLeaf(pub u32);

/// A leaf of a left cluster's tree.
///
/// Leaf 0 is the STOP leaf; leaf `1 + r` codes `Right(r)`, so
/// `LeftLeaf::from(right)` and [`LeftLeaf::right`] convert between the two.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(transparent)]
pub struct LeftLeaf(pub u32);

impl Char {
    /// The word id of this character: a character is its own word.
    pub fn word(self) -> Word {
        Word(self.0)
    }
}

impl LeftLeaf {
    /// The STOP leaf: leaf 0 of every left cluster's tree.
    pub const STOP: LeftLeaf = LeftLeaf(0);

    /// The right cluster this leaf codes; `None` for the STOP leaf.
    pub fn right(self) -> Option<Right> {
        Some(Right(self.0.checked_sub(1)?))
    }
}

impl From<Right> for LeftLeaf {
    fn from(right: Right) -> LeftLeaf {
        LeftLeaf(right.0 + 1)
    }
}

/// What a word is: a character, or a rule that expands to two words.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CharOrRule {
    /// The word is a character of the alphabet.
    Char(Char),
    /// The word is the one a rule defines.
    Rule(Rule),
}

/// The tree that codes the right clusters: one per left cluster
/// (`STANDARD.md` §4).
///
/// Leaf 0 is the STOP leaf and leaf `1 + r` codes right cluster `r`.
#[derive(Clone, Debug)]
pub struct TopTree(Tree);

impl TopTree {
    fn from_depths(depths: &[u32]) -> TopTree {
        TopTree(Tree::from_depths(depths))
    }

    /// The number of leaves, the STOP leaf included: `kq + 1`.
    pub fn num_leaves(&self) -> u32 {
        self.0.num_leaves()
    }

    /// Append the codeword of `leaf`, most significant bit first.
    pub(crate) fn write(&self, writer: &mut BitWriter, leaf: LeftLeaf) -> Result<(), Error> {
        self.0.write(writer, leaf.0)
    }

    /// Read one codeword and return its leaf.
    pub(crate) fn read(&self, reader: &mut BitReader<'_>) -> Result<LeftLeaf, Error> {
        self.0.read(reader).map(LeftLeaf)
    }
}

/// The tree that codes the words of one right cluster (`STANDARD.md` §4).
///
/// Its leaves are [`RightLeaf`]s: positions in the cluster's ascending word
/// list.  A cluster with no words has an empty tree: there is no leaf to name,
/// so reading it fails and every write names a leaf that does not exist.  The model format allows such a cluster (§2 invariant 7).
#[derive(Clone, Debug)]
pub struct BottomTree(Tree);

impl BottomTree {
    fn from_depths(depths: &[u32]) -> BottomTree {
        BottomTree(Tree::from_depths(depths))
    }

    /// The number of leaves: the number of words in this right cluster.
    pub fn num_leaves(&self) -> u32 {
        self.0.num_leaves()
    }

    /// Append the codeword of `leaf`, most significant bit first.
    pub(crate) fn write(&self, writer: &mut BitWriter, leaf: RightLeaf) -> Result<(), Error> {
        self.0.write(writer, leaf.0)
    }

    /// Read one codeword and return its leaf.
    pub(crate) fn read(&self, reader: &mut BitReader<'_>) -> Result<RightLeaf, Error> {
        self.0.read(reader).map(RightLeaf)
    }
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

/// Decode exactly `nchars` characters of UTF-8: `(alphabet, bytes used)`.
///
/// The header counts characters, not bytes.  UTF-8 delimits itself, so the
/// section ends where the `nchars`-th character ends; an ASCII alphabet is one
/// byte a character, which is why the shipped file's section is `nchars` bytes.
/// A byte that cannot start a sequence, or a sequence that is not valid UTF-8,
/// is a model error rather than a replacement character.
fn read_alphabet(
    buf: &[u8],
    pos: usize,
    nchars: u32,
) -> Result<(Vec<char>, usize), Error> {
    let mut alphabet = Vec::with_capacity(
        (nchars as usize).min(buf.len().saturating_sub(pos)),
    );
    let mut p = pos;
    while (alphabet.len() as u32) < nchars {
        let b = *buf.get(p).ok_or(Error::Truncated("truncated alphabet"))?;
        let len = match b {
            0x00..=0x7f => 1,
            0xc2..=0xdf => 2,
            0xe0..=0xef => 3,
            0xf0..=0xf4 => 4,
            _ => return Err(Error::Model("the alphabet is not valid UTF-8")),
        };
        let end = p
            .checked_add(len)
            .filter(|&end| end <= buf.len())
            .ok_or(Error::Truncated("truncated alphabet"))?;
        let s = std::str::from_utf8(&buf[p..end])
            .map_err(|_| Error::Model("the alphabet is not valid UTF-8"))?;
        let mut chars = s.chars();
        let c = chars.next().expect("a non-empty UTF-8 slice");
        if chars.next().is_some() {
            return Err(Error::Model("the alphabet is not valid UTF-8"));
        }
        alphabet.push(c);
        p = end;
    }
    Ok((alphabet, p - pos))
}

/// The pair table: which rule merges an ordered pair of words.
///
/// Open addressing with linear probing.  A bucket holds only the rule, because
/// the rule's children *are* the key: [`Model::children`] recovers them for the
/// comparison, so no slot pays for a stored pair or a hash.  Four bytes a slot
/// at a load of at most one half keeps the whole table in a handful of cache
/// lines and a probe to one or two buckets.
#[derive(Clone, Debug)]
struct RuleIndex {
    /// [`EMPTY`], or the rule whose children hash to this bucket.
    slots: Vec<u32>,
}

/// The empty marker.  A model cannot hold `u32::MAX` rules: its words are
/// `nchars + rule` in a `u32`, so the ids run out first.
const EMPTY: u32 = u32::MAX;

impl RuleIndex {
    /// Index `rules`, which the model has already checked: the child ids exist
    /// and no pair repeats, so a bucket's rule is the only rule for its key.
    fn with_rules(rules: &[(Word, Word)]) -> RuleIndex {
        let mut len = 8;
        while len < rules.len() * 2 {
            len *= 2;
        }
        let mut index = RuleIndex {
            slots: vec![EMPTY; len],
        };
        for (rank, &(a, b)) in rules.iter().enumerate() {
            index.insert(Rule(rank as u32), a, b);
        }
        index
    }

    /// The bucket `a b` hashes to.
    ///
    /// Fibonacci hashing: multiply the pair, packed into one word, by a fixed
    /// odd constant and take the top bits, which move every bit of the key.
    fn start(&self, a: Word, b: Word) -> usize {
        let key = ((a.0 as u64) << 32) | b.0 as u64;
        let mixed = key.wrapping_mul(0x9E37_79B9_7F4A_7C15);
        (mixed >> (64 - self.slots.len().trailing_zeros())) as usize
    }

    /// The rule for `a b`, if the model has one.
    fn get(&self, rules: &[(Word, Word)], a: Word, b: Word) -> Option<Rule> {
        let mask = self.slots.len() - 1;
        let mut at = self.start(a, b);
        loop {
            let slot = self.slots[at];
            if slot == EMPTY {
                return None;
            }
            if rules[slot as usize] == (a, b) {
                return Some(Rule(slot));
            }
            at = (at + 1) & mask;
        }
    }

    /// Add `rule`, whose children are `a b`.  The table is never full, so the
    /// scan for an empty bucket ends.
    fn insert(&mut self, rule: Rule, a: Word, b: Word) {
        let mask = self.slots.len() - 1;
        let mut at = self.start(a, b);
        while self.slots[at] != EMPTY {
            at = (at + 1) & mask;
        }
        self.slots[at] = rule.0;
    }
}

/// A loaded model: the tables plus every derived view the codec needs.
///
/// The sizes are not stored separately: the vocabulary is the alphabet plus the
/// rule list, the left clusters are the trees that code right clusters, and the
/// right clusters are the word lists.
#[derive(Clone, Debug)]
pub struct Model {
    /// The alphabet size: word ids below this are characters.
    nchars: u32,
    /// `q` in `STANDARD.md`: right clusters per left cluster.
    q: u32,
    alphabet: Vec<char>,
    rules: Vec<(Word, Word)>,
    memberships: Vec<Right>,
    char_id: HashMap<char, Char>,
    cluster_ids: Vec<Vec<Word>>,
    pos_in_cluster: Vec<RightLeaf>,
    bottom_trees: Vec<BottomTree>,
    top_trees: Vec<TopTree>,
    /// The rules indexed by the pair they merge.
    rule_index: RuleIndex,
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
        // `a != b` rejects a run word; the set rejects a second id for a word
        // the file already defines, which the encoder's pair map cannot
        // represent.  Both catch a rule stream read past its end: padding
        // zeros decode as `(0, 0)`.
        let mut seen = HashSet::with_capacity(rules.len());
        for (i, &(a, b)) in rules.iter().enumerate() {
            let n = nchars + i as u32;
            if a >= n || b >= n {
                return Err(Error::Model("a rule names a child that does not exist"));
            }
            if a == b {
                return Err(Error::Model("a rule names the same child twice"));
            }
            if !seen.insert((a, b)) {
                return Err(Error::Model("two rules name the same pair of children"));
            }
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
            .map(|(i, &c)| (c, Char(i as u32)))
            .collect();

        let mut cluster_ids: Vec<Vec<Word>> = vec![Vec::new(); kq as usize];
        for (word, &right) in memberships.iter().enumerate() {
            if right >= kq {
                return Err(Error::Model(
                    "a membership names a cluster that does not exist",
                ));
            }
            cluster_ids[right as usize].push(Word(word as u32));
        }
        let mut pos_in_cluster = vec![RightLeaf(0); v as usize];
        let mut bottom_trees = Vec::with_capacity(kq as usize);
        for ids in cluster_ids.iter() {
            let depths: Vec<u32> = ids
                .iter()
                .map(|&Word(word)| bottom_depths[word as usize])
                .collect();
            require_kraft(&depths)?;
            for (position, &word) in ids.iter().enumerate() {
                pos_in_cluster[word.0 as usize] = RightLeaf(position as u32);
            }
            bottom_trees.push(BottomTree::from_depths(&depths));
        }

        let top_trees: Vec<TopTree> = top_depths
            .iter()
            .map(|depths| TopTree::from_depths(depths))
            .collect();

        let rules: Vec<(Word, Word)> = rules
            .into_iter()
            .map(|(a, b)| (Word(a), Word(b)))
            .collect();
        let memberships: Vec<Right> = memberships.into_iter().map(Right).collect();
        let rule_index = RuleIndex::with_rules(&rules);

        Ok(Model {
            nchars,
            q,
            alphabet,
            rules,
            memberships,
            char_id,
            cluster_ids,
            pos_in_cluster,
            bottom_trees,
            top_trees,
            rule_index,
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
        if v < nchars || v > u32::MAX as u64 || k == 0 || q == 0 || k > 1 << 16 {
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
            rules.push((a, b));
        }
        // The table is exactly as long as its rules: the padding is not a
        // place to hide bytes, and the alphabet starts where they end.
        if (reader.position() + 7) / 8 != rules_len {
            return Err(Error::Model(
                "the rule table's length is not the length of its rules",
            ));
        }
        pos = end;

        let (alphabet, used) = read_alphabet(buf, pos, nchars)?;
        pos += used;

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

    // ------------------------------------------------------------- sizes
    //
    // The names here are the type names, not the single letters of
    // `STANDARD.md`; each docstring gives the letter it corresponds to.

    /// The number of characters — `C` in `STANDARD.md`, `nchars` in the file.
    pub fn num_chars(&self) -> u32 {
        self.nchars
    }
    /// The number of rules — `V − C` in `STANDARD.md`.
    pub fn num_rules(&self) -> u32 {
        self.rules.len() as u32
    }
    /// The vocabulary size — `V` in `STANDARD.md`.
    pub fn num_words(&self) -> u32 {
        self.nchars + self.num_rules()
    }
    /// The number of left clusters — `k` in `STANDARD.md`.
    pub fn num_lefts(&self) -> u32 {
        self.top_trees.len() as u32
    }
    /// The number of right clusters — `kq` in `STANDARD.md`.
    pub fn num_rights(&self) -> u32 {
        self.cluster_ids.len() as u32
    }
    /// The number of right clusters per left cluster — `q` in `STANDARD.md`.
    pub fn num_rights_per_left(&self) -> u32 {
        self.q
    }

    // ------------------------------------------------------------- lookups

    /// The character at an index.
    pub fn char_at(&self, at: Char) -> Result<char, Error> {
        self.alphabet
            .get(at.0 as usize)
            .copied()
            .ok_or(Error::Model("a character index is outside the alphabet"))
    }
    /// A character's index, if the model has that character.
    pub fn char_id(&self, c: char) -> Option<Char> {
        self.char_id.get(&c).copied()
    }
    /// The two words a rule merges.
    pub fn children(&self, rule: Rule) -> Result<(Word, Word), Error> {
        self.rules
            .get(rule.0 as usize)
            .copied()
            .ok_or(Error::Model("a rule is outside the model"))
    }
    /// The word a rule defines: `num_chars() + rule`.
    pub fn word_of_rule(&self, rule: Rule) -> Word {
        Word(self.nchars + rule.0)
    }
    /// What a word is: a character, or a rule.
    pub fn parts(&self, word: Word) -> Result<CharOrRule, Error> {
        if word.0 < self.nchars {
            Ok(CharOrRule::Char(Char(word.0)))
        } else if word.0 < self.num_words() {
            Ok(CharOrRule::Rule(Rule(word.0 - self.nchars)))
        } else {
            Err(Error::Model("a word is outside the model"))
        }
    }
    /// The rule that merges an adjacent pair of words, if the model has one.
    pub fn rule_for(&self, a: Word, b: Word) -> Option<Rule> {
        self.rule_index.get(&self.rules, a, b)
    }
    /// The right cluster a word belongs to.
    pub fn right(&self, word: Word) -> Result<Right, Error> {
        self.memberships
            .get(word.0 as usize)
            .copied()
            .ok_or(Error::Model("a word is outside the model"))
    }
    /// The left cluster a word starts in.
    pub fn left(&self, word: Word) -> Result<Left, Error> {
        self.left_of(self.right(word)?)
    }
    /// The left cluster that owns a right cluster: `right / q`.
    pub fn left_of(&self, right: Right) -> Result<Left, Error> {
        let left = Left(right.0 / self.q);
        if left.0 < self.num_lefts() {
            Ok(left)
        } else {
            Err(Error::Model("a right cluster is outside the model"))
        }
    }
    /// The position of a word in its right cluster's word list.
    pub fn position(&self, word: Word) -> Result<RightLeaf, Error> {
        self.pos_in_cluster
            .get(word.0 as usize)
            .copied()
            .ok_or(Error::Model("a word is outside the model"))
    }
    /// The word at a position in a right cluster's word list.
    pub fn word_at(&self, right: Right, at: RightLeaf) -> Result<Word, Error> {
        self.cluster_ids
            .get(right.0 as usize)
            .and_then(|ids| ids.get(at.0 as usize))
            .copied()
            .ok_or(Error::Model("a word position is outside its cluster"))
    }
    /// The tree of a left cluster.
    pub fn top_tree(&self, left: Left) -> Result<&TopTree, Error> {
        self.top_trees
            .get(left.0 as usize)
            .ok_or(Error::Model("a left cluster is outside the model"))
    }
    /// The tree of a right cluster.
    ///
    /// A cluster with no words has an empty tree, whose leaves are none: it is
    /// returned like any other, and reading from it fails.
    pub fn bottom_tree(&self, right: Right) -> Result<&BottomTree, Error> {
        self.bottom_trees
            .get(right.0 as usize)
            .ok_or(Error::Model("a right cluster is outside the model"))
    }

    /// One line describing the model, for logs and the CLI.
    pub fn info(&self) -> String {
        format!(
            "V={} k={} q={} alphabet={} rules={} kq={}",
            self.num_words(),
            self.num_lefts(),
            self.q,
            self.nchars,
            self.num_rules(),
            self.num_rights()
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bitio::BitWriter;
    use crate::ladder::{ladder_put, put_varint};
    use crate::Codec;

    /// The same fixture `python/tests/test_varnames.py` builds: `V = 4`,
    /// `k = q = 1`, alphabet `aé`.  Two characters, three bytes, so the
    /// header's `nchars` and the section's length have to differ.
    fn tiny_utf8_model() -> Vec<u8> {
        tiny_utf8_model_with(&[(0u32, 1u32), (0, 2)])
    }

    fn tiny_utf8_model_with(pairs: &[(u32, u32)]) -> Vec<u8> {
        let mut rules = BitWriter::new();
        for (i, &(a, b)) in pairs.iter().enumerate() {
            let n = 2 + i as u32;
            ladder_put(&mut rules, a, n);
            ladder_put(&mut rules, b, n);
        }
        let rules = rules.finish();
        let mut buf = Vec::new();
        buf.extend_from_slice(b"NVM1");
        put_varint(4, &mut buf);
        put_varint(1, &mut buf);
        put_varint(1, &mut buf);
        put_varint(2, &mut buf);
        put_varint(rules.as_bytes().len() as u64, &mut buf);
        buf.extend_from_slice(rules.as_bytes());
        buf.extend_from_slice("aé".as_bytes());
        buf.extend_from_slice(&[0, 0]); // bottom depths: 4 leaves, 4 bits each
        buf.extend_from_slice(&[0]); // top depths: 2 leaves, 4 bits each
        buf
    }

    #[test]
    fn the_alphabet_is_utf8() {
        let buf = tiny_utf8_model();
        assert_eq!(buf.len(), 17);
        let model = Model::from_bytes(&buf).expect("a valid model");
        assert_eq!(model.num_chars(), 2);
        assert_eq!(model.char_at(Char(0)), Ok('a'));
        assert_eq!(model.char_at(Char(1)), Ok('é'));
        let codec = Codec::new(model);
        let bits = codec.encode_bits("aé").expect("an encodable name");
        assert_eq!(bits.len(), 2);
        let code = codec.encode("aé").expect("an encodable name");
        assert_eq!(codec.decode(code).expect("a decodable code"), "aé");
    }

    #[test]
    fn lookups_check_their_index() {
        let model = Model::from_bytes(&tiny_utf8_model()).expect("a valid model");
        // V = 4: the characters `a` and `é`, then the two rules' words.
        assert_eq!(model.parts(Char(1).word()), Ok(CharOrRule::Char(Char(1))));
        assert_eq!(
            model.parts(model.word_of_rule(Rule(1))),
            Ok(CharOrRule::Rule(Rule(1)))
        );
        assert!(model.parts(Word(4)).is_err());
        assert!(model.children(Rule(2)).is_err());
        assert!(model.char_at(Char(2)).is_err());
        // The fixture's rules are `(a,é)` and `(a, (a,é))`, in that order.
        assert_eq!(model.rule_for(Word(0), Word(1)), Some(Rule(0)));
        assert_eq!(model.rule_for(Word(1), Word(0)), None);
        // One right cluster, so its word list is every word in id order.
        let first_rule_word = model.word_of_rule(Rule(0));
        assert_eq!(model.right(first_rule_word), Ok(Right(0)));
        assert_eq!(model.position(first_rule_word), Ok(RightLeaf(2)));
        assert_eq!(model.left_of(Right(0)), Ok(Left(0)));
    }

    #[test]
    fn a_left_leaf_is_a_right_cluster_plus_one() {
        assert_eq!(LeftLeaf::STOP.right(), None);
        assert_eq!(LeftLeaf::from(Right(7)), LeftLeaf(8));
        assert_eq!(LeftLeaf::from(Right(7)).right(), Some(Right(7)));
    }

    /// `V = 4`, `k = 1`, `q = 2`, alphabet `aé`: every word is in right
    /// cluster 0, so cluster 1 is empty.  The top tree still names both,
    /// because its `kq + 1` leaves are fixed whatever the clusters contain.
    fn a_model_with_an_empty_cluster() -> Vec<u8> {
        let mut rules = BitWriter::new();
        for (i, &(a, b)) in [(0u32, 1u32), (0, 2)].iter().enumerate() {
            let n = 2 + i as u32;
            ladder_put(&mut rules, a, n);
            ladder_put(&mut rules, b, n);
        }
        let rules = rules.finish();
        let mut buf = Vec::new();
        buf.extend_from_slice(b"NVM1");
        put_varint(4, &mut buf); // V
        put_varint(1, &mut buf); // k
        put_varint(2, &mut buf); // q
        put_varint(2, &mut buf); // nchars
        put_varint(rules.as_bytes().len() as u64, &mut buf);
        buf.extend_from_slice(rules.as_bytes());
        buf.extend_from_slice("aé".as_bytes());
        // memberships: one bit a word, and all four say cluster 0
        buf.extend_from_slice(&[0]);
        // Word depths: cluster 0's four words, four bits each, deltas all 0;
        // cluster 1 has no words and so contributes no bits at all.
        buf.extend_from_slice(&[0, 0]);
        // Cluster depths: STOP and two right clusters, deltas 2,1,2 --
        // nibbles 2,1,2 packed low first, STOP the deepest.
        buf.extend_from_slice(&[0x12, 0x02]);
        buf
    }

    #[test]
    fn a_cluster_with_no_words_has_an_empty_tree() {
        let model = Model::from_bytes(&a_model_with_an_empty_cluster()).expect("a valid model");
        assert_eq!((model.num_words(), model.num_rights()), (4, 2));
        assert_eq!(model.right(Word(0)), Ok(Right(0)));
        assert_eq!(model.bottom_tree(Right(0)).unwrap().num_leaves(), 4);
        // The empty cluster is a tree like any other: no leaves, no codewords.
        let empty = model.bottom_tree(Right(1)).expect("a tree, though empty");
        assert_eq!(empty.num_leaves(), 0);
        assert!(matches!(
            empty.read(&mut BitReader::new(&[0xff])),
            Err(Error::EmptyTree)
        ));
        // Encoding never reaches it, and the round trip is unaffected.
        let codec = Codec::new(model);
        let code = codec.encode("aé").expect("an encodable name");
        assert_eq!(codec.decode(code).expect("a decodable code"), "aé");
        // The top tree's codeword `01` names the empty cluster.
        assert!(matches!(codec.decode(2), Err(Error::EmptyTree)));
    }

    #[test]
    fn a_model_without_words_is_legal() {
        let mut buf = Vec::new();
        buf.extend_from_slice(b"NVM1");
        put_varint(2, &mut buf); // v: two characters and no rules
        put_varint(1, &mut buf);
        put_varint(1, &mut buf);
        put_varint(2, &mut buf);
        put_varint(0, &mut buf); // no rule bytes
        buf.extend_from_slice("aé".as_bytes());
        buf.extend_from_slice(&[0]); // bottom depths: two leaves at depth 1
        buf.extend_from_slice(&[0]); // top depths: STOP and one right cluster
        let model = Model::from_bytes(&buf).expect("v == nchars is legal");
        assert_eq!(model.num_rules(), 0);
        let codec = Codec::new(model);
        let code = codec.encode("aé").expect("an encodable name");
        assert_eq!(codec.decode(code).expect("a decodable code"), "aé");
    }

    #[test]
    fn a_broken_alphabet_byte_is_refused() {
        let mut buf = tiny_utf8_model();
        let start = 4 + 4 + 1 + 2; // magic, header, rules length, rules
        buf[start + 1] = 0xff; // the lead byte of é
        assert!(matches!(Model::from_bytes(&buf), Err(Error::Model(_))));
    }

    #[test]
    fn a_rule_naming_one_child_twice_is_refused() {
        let buf = tiny_utf8_model_with(&[(0, 0), (0, 2)]);
        assert!(matches!(
            Model::from_bytes(&buf),
            Err(Error::Model("a rule names the same child twice"))
        ));
    }

    #[test]
    fn a_repeated_rule_is_refused() {
        let buf = tiny_utf8_model_with(&[(0, 1), (0, 1)]);
        assert!(matches!(
            Model::from_bytes(&buf),
            Err(Error::Model("two rules name the same pair of children"))
        ));
    }

    #[test]
    fn a_rule_table_with_a_spare_byte_is_refused() {
        let mut buf = tiny_utf8_model();
        buf[8] += 1; // the length varint: two bytes -> three
        buf.insert(11, 0); // one byte of slack in the table
        assert!(matches!(
            Model::from_bytes(&buf),
            Err(Error::Model(
                "the rule table's length is not the length of its rules"
            ))
        ));
    }

    #[test]
    fn a_rule_table_too_short_for_its_rules_is_refused() {
        let mut buf = tiny_utf8_model();
        buf[8] -= 1; // the length varint: two bytes -> one
        buf.remove(10); // and the second byte of the table
        assert!(matches!(
            Model::from_bytes(&buf),
            Err(Error::Model(
                "the rule table's length is not the length of its rules"
            ))
        ));
    }

    #[test]
    fn the_pair_index_agrees_with_a_map_of_the_rules() {
        let codec = crate::standard::standard();
        let model = codec.model();
        let mut map = HashMap::with_capacity(model.num_rules() as usize);
        for rank in 0..model.num_rules() {
            let rule = Rule(rank);
            let (a, b) = model.children(rule).expect("a rule");
            assert_eq!(model.rule_for(a, b), Some(rule), "rule {rank}");
            map.insert((a, b), rule);
        }
        // A dense block of small ids -- characters and the words built out of
        // them -- which is where the probe chains sit and where a bucket that
        // forgot to compare its key would show.
        for a in 0..200u32 {
            for b in 0..200u32 {
                let (a, b) = (Word(a), Word(b));
                assert_eq!(
                    model.rule_for(a, b),
                    map.get(&(a, b)).copied(),
                    "{a:?} {b:?}"
                );
            }
        }
    }

    #[test]
    fn a_zero_filled_rule_stream_is_refused() {
        // Read past its end, the ladder gives `(0, 0)` for every rule.
        let mut buf = tiny_utf8_model();
        let start = 4 + 4 + 1; // magic, the four header varints, the length
        let end = start + 2; // the rule bytes of this fixture
        buf[start..end].fill(0);
        assert!(matches!(
            Model::from_bytes(&buf),
            Err(Error::Model("a rule names the same child twice"))
        ));
    }
}

//! The codec: identifier ↔ bit string ↔ integer (`ENCODING.md` §2).
//!
//! The code alternates two steps: *which right cluster comes next, given the
//! left cluster we are in*, then *which word in that right cluster*.  An
//! identifier starts in left cluster 0 by convention and ends when the top
//! stage reaches its STOP leaf, whose codeword is all zeros — also the padding
//! above the integer, so the end costs nothing and is not stored.

use std::cmp::Reverse;
use std::collections::{BinaryHeap, HashMap};

use crate::bitio::{Bits, BitWriter};
use crate::model::Model;
use crate::Error;

/// The identifier terminates after this many symbols, whatever the bits say.
const MAX_SYMBOLS: usize = 1_000_000;

/// An integer code and its exact bit length.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Code {
    /// The integer; bit *i* is the *i*-th bit of the codeword.
    pub value: u128,
    /// The number of bits the code occupies.
    pub bits: u32,
}

impl Code {
    /// The codeword as a bit string, trailing zeros stripped.
    pub fn to_bits(self) -> Bits {
        Bits::from_u128(self.value)
    }
}

/// Ties a [`Model`] to the encoding loop.
#[derive(Clone)]
pub struct Codec {
    model: Model,
}

impl Codec {
    /// Tie a model to the encoding loop.
    pub fn new(model: Model) -> Self {
        Codec { model }
    }

    /// The model this codec encodes with.
    pub fn model(&self) -> &Model {
        &self.model
    }

    // ------------------------------------------------------------- encoding

    /// Split an identifier into the model's symbols (`ENCODING.md` §1).
    pub fn tokenise(&self, identifier: &str) -> Result<Vec<u32>, Error> {
        let mut tokens = Vec::with_capacity(identifier.len());
        for c in identifier.chars() {
            tokens.push(
                self.model
                    .char_id(c)
                    .ok_or(Error::UnknownCharacter(c))?,
            );
        }
        Ok(merge_pairs(tokens, self.model.plan()))
    }

    /// The codeword as a bit string, stream order, trailing zeros cut.
    pub fn encode_bits(&self, identifier: &str) -> Result<Bits, Error> {
        let tokens = self.tokenise(identifier)?;
        let mut writer = BitWriter::new();
        let mut left = 0u32;
        for symbol in tokens {
            let cluster = self.model.cluster_of(symbol)?;
            self.model
                .top_tree(left)
                .write(&mut writer, 1 + cluster as usize)?;
            let tree = self
                .model
                .bottom_tree(cluster)
                .ok_or(Error::EmptyCluster(cluster))?;
            tree.write(&mut writer, self.model.position_of(symbol)? as usize)?;
            left = self.model.left_cluster(symbol);
        }
        self.model.top_tree(left).write(&mut writer, 0)?; // the STOP leaf
        Ok(writer.finish())
    }

    /// The integer code for an identifier.
    ///
    /// Fails with [`Error::CodeTooLong`] if the code needs more than 128 bits;
    /// use [`Codec::encode_bits`] for those.
    pub fn encode(&self, identifier: &str) -> Result<Code, Error> {
        let bits = self.encode_bits(identifier)?;
        let value = bits.to_u128().ok_or(Error::CodeTooLong { bits: bits.len() })?;
        Ok(Code {
            value,
            bits: bits.len() as u32,
        })
    }

    // ------------------------------------------------------------- decoding

    /// Decode a bit string; bits past the end read as zeros.
    pub fn decode_bits(&self, bits: &Bits) -> Result<String, Error> {
        let mut reader = bits.reader();
        let mut tokens = Vec::new();
        let mut left = 0u32;
        for _ in 0..MAX_SYMBOLS {
            let slot = self.model.top_tree(left).read(&mut reader)?;
            if slot == 0 {
                return self.spell(&tokens);
            }
            let cluster = slot - 1;
            let tree = self
                .model
                .bottom_tree(cluster)
                .ok_or(Error::EmptyCluster(cluster))?;
            let position = tree.read(&mut reader)?;
            tokens.push(self.model.symbol_of(cluster, position)?);
            left = self.model.left_cluster(*tokens.last().unwrap());
        }
        Err(Error::DoesNotTerminate)
    }

    /// Decode an integer code.
    pub fn decode(&self, value: u128) -> Result<String, Error> {
        self.decode_bits(&Bits::from_u128(value))
    }

    /// Word ids back to characters, by replaying the rule list.
    fn spell(&self, tokens: &[u32]) -> Result<String, Error> {
        let model = &self.model;
        let v = model.v() as usize;
        let mut text: Vec<Option<String>> = vec![None; v];
        for (i, c) in model.alphabet().iter().enumerate() {
            text[i] = Some(c.to_string());
        }
        for (rank, &(a, b)) in model.rules().iter().enumerate() {
            let left = text[a as usize].as_deref().unwrap_or("");
            let right = text[b as usize].as_deref().unwrap_or("");
            text[model.nchars() as usize + rank] = Some(format!("{left}{right}"));
        }
        let mut out = String::new();
        for &symbol in tokens {
            match text.get(symbol as usize).and_then(|t| t.as_ref()) {
                Some(s) => out.push_str(s),
                None => return Err(Error::Model("a token is outside the model")),
            }
        }
        Ok(out)
    }
}

/// The production tokeniser of `ENCODING.md` §1, in one pass.
///
/// Ranks are nested — a merge's rank exceeds the ranks that built its operands
/// — so sweeping ranks in ascending order and merging every still-valid pair
/// performs the same merges as repeatedly taking the lowest rank.  A linked
/// list over positions makes it linear; the heap holds ranks, never positions.
/// A rank can be exhausted and later seen again, so the heap may hold
/// duplicates and the bucket table is the authority.
pub fn merge_pairs(tokens: Vec<u32>, plan: &HashMap<(u32, u32), (u32, u32)>) -> Vec<u32> {
    let n = tokens.len();
    if n < 2 || plan.is_empty() {
        return tokens;
    }
    let mut next: Vec<usize> = (1..=n).collect();
    let mut prev: Vec<isize> = (0..n).map(|i| i as isize - 1).collect();
    let mut dead = vec![false; n];
    let mut value = tokens;
    let mut buckets: HashMap<u32, Vec<usize>> = HashMap::new();
    let mut heap: BinaryHeap<Reverse<u32>> = BinaryHeap::new();

    fn push(
        i: usize,
        n: usize,
        next: &[usize],
        dead: &[bool],
        value: &[u32],
        plan: &HashMap<(u32, u32), (u32, u32)>,
        buckets: &mut HashMap<u32, Vec<usize>>,
        heap: &mut BinaryHeap<Reverse<u32>>,
    ) {
        let j = next[i];
        if j >= n || dead[j] {
            return;
        }
        if let Some(&(rank, _)) = plan.get(&(value[i], value[j])) {
            match buckets.get_mut(&rank) {
                Some(bucket) => bucket.push(i),
                None => {
                    buckets.insert(rank, vec![i]);
                    heap.push(Reverse(rank));
                }
            }
        }
    }

    for i in 0..n - 1 {
        push(
            i, n, &next, &dead, &value, plan, &mut buckets, &mut heap,
        );
    }
    while let Some(&Reverse(rank)) = heap.peek() {
        if !buckets.contains_key(&rank) {
            heap.pop(); // a stale entry for a rank whose bucket is gone
            continue;
        }
        if buckets[&rank].is_empty() {
            heap.pop();
            buckets.remove(&rank);
            continue;
        }
        let i = buckets.get_mut(&rank).unwrap().pop().unwrap();
        if dead[i] {
            continue;
        }
        let j = next[i];
        if j >= n || dead[j] {
            continue;
        }
        let Some(&(found, new_id)) = plan.get(&(value[i], value[j])) else {
            continue;
        };
        if found != rank {
            continue;
        }
        value[i] = new_id;
        dead[j] = true;
        next[i] = next[j];
        let following = next[j];
        if following < n {
            prev[following] = i as isize;
        }
        for k in [prev[i], i as isize] {
            if k >= 0 && !dead[k as usize] {
                push(
                    k as usize,
                    n,
                    &next,
                    &dead,
                    &value,
                    plan,
                    &mut buckets,
                    &mut heap,
                );
            }
        }
    }

    let mut out = Vec::with_capacity(n);
    let mut i = 0;
    while i < n {
        out.push(value[i]);
        i = next[i];
    }
    out
}

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

    /// Word ids back to characters, expanding only the tokens that are present.
    ///
    /// A rule names children whose ids are smaller than its own — [`Model`]
    /// rejects any other rule — so expansion is a walk down a finite tree, and
    /// the tokens of one identifier are all it needs.  The rule list is never
    /// replayed, so the cost follows the output, not the model.
    fn spell(&self, tokens: &[u32]) -> Result<String, Error> {
        let model = &self.model;
        let first_rule = model.nchars() as usize;
        let mut out = String::with_capacity(tokens.len());
        let mut stack: Vec<u32> = tokens.iter().rev().copied().collect();
        while let Some(symbol) = stack.pop() {
            let symbol = symbol as usize;
            if symbol < first_rule {
                let c = *model
                    .alphabet()
                    .get(symbol)
                    .ok_or(Error::Model("a token is outside the model"))?;
                out.push(c);
            } else {
                let &(a, b) = model
                    .rules()
                    .get(symbol - first_rule)
                    .ok_or(Error::Model("a token is outside the model"))?;
                stack.push(b); // the left operand comes off the stack first
                stack.push(a);
            }
        }
        Ok(out)
    }
}

/// A live token: a word id and its neighbours in the identifier.
///
/// A merge keeps the left token and removes the right one, so the head of the
/// list is always token 0 and the tail has no `next`.
#[derive(Clone, Copy)]
struct Token {
    word: u32,
    next: Option<usize>,
    prev: Option<usize>,
}

/// The state of one `merge_pairs` call: the sweep of `ENCODING.md` §1.
///
/// Ranks are nested — a merge's rank exceeds the ranks that built its operands
/// — so any pair a merge creates has a rank above the one just used, and a
/// sweep that always takes the lowest rank performs the merges in the order
/// the model defines.  `(rank, position)` in the heap gives the lowest rank
/// first and the leftmost of a rank, which is exactly the tie-break.
struct MergePairs<'a> {
    /// `None` where a token has been merged away.
    tokens: Vec<Option<Token>>,
    plan: &'a HashMap<(u32, u32), (u32, u32)>,
    heap: BinaryHeap<Reverse<(u32, usize)>>,
}

impl<'a> MergePairs<'a> {
    /// A sweep over `tokens`, whose adjacent pairs are looked up in `plan`.
    fn new(tokens: Vec<u32>, plan: &'a HashMap<(u32, u32), (u32, u32)>) -> Self {
        let n = tokens.len();
        let tokens = tokens
            .into_iter()
            .enumerate()
            .map(|(i, word)| {
                Some(Token {
                    word,
                    next: (i + 1 < n).then_some(i + 1),
                    prev: i.checked_sub(1),
                })
            })
            .collect();
        MergePairs {
            tokens,
            plan,
            heap: BinaryHeap::new(),
        }
    }

    /// Offer the pair that starts at `i`, if the model has a rule for it.
    fn push(&mut self, i: usize) {
        let Some(Token { word, next: Some(j), .. }) = self.tokens[i] else {
            return;
        };
        let Some(right) = self.tokens[j] else { return };
        if let Some(&(rank, _)) = self.plan.get(&(word, right.word)) {
            self.heap.push(Reverse((rank, i)));
        }
    }

    /// Merge until no adjacent pair has a rule; return the surviving words.
    fn run(mut self) -> Vec<u32> {
        for i in 0..self.tokens.len().saturating_sub(1) {
            self.push(i);
        }
        while let Some(Reverse((rank, i))) = self.heap.pop() {
            // The pair at `i` may have gone, or changed, since it was queued.
            let Some(Token { word, next: Some(j), prev }) = self.tokens[i] else {
                continue;
            };
            let Some(right) = self.tokens[j] else { continue };
            let Some(&(found, new_word)) = self.plan.get(&(word, right.word)) else {
                continue;
            };
            if found != rank {
                continue; // stale: the pair at `i` is not the one we queued
            }
            let following = right.next;
            self.tokens[i] = Some(Token {
                word: new_word,
                next: following,
                prev,
            });
            self.tokens[j] = None;
            if let Some(f) = following {
                if let Some(after) = self.tokens[f].as_mut() {
                    after.prev = Some(i);
                }
            }
            // The pair before `i` is new too, because `i`'s word has changed.
            if let Some(p) = prev {
                self.push(p);
            }
            self.push(i);
        }
        let mut out = Vec::with_capacity(self.tokens.len());
        let mut cursor = Some(0);
        while let Some(i) = cursor {
            let Some(token) = self.tokens[i] else { break };
            out.push(token.word);
            cursor = token.next;
        }
        out
    }
}

/// The production tokeniser of `ENCODING.md` §1, in one pass.
///
/// A linked list over the positions makes each merge a constant amount of work
/// besides the heap; the heap holds one entry per candidate pair, and entries
/// whose pair has since changed are skipped when they surface.
pub fn merge_pairs(tokens: Vec<u32>, plan: &HashMap<(u32, u32), (u32, u32)>) -> Vec<u32> {
    if tokens.len() < 2 || plan.is_empty() {
        return tokens;
    }
    MergePairs::new(tokens, plan).run()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::standard;

    #[test]
    fn spelling_is_the_expansion_of_the_tokens_alone() {
        let codec = standard().expect("the embedded tables");
        let model = codec.model();
        let first_rule = model.nchars() as usize;
        assert_eq!(codec.spell(&[]).unwrap(), "");
        assert_eq!(codec.spell(&[0]).unwrap(), model.alphabet()[0].to_string());
        // The first rule is the first pair of the rule list, in order.
        let (a, b) = model.rules()[0];
        let expected: String = [a, b]
            .iter()
            .map(|&t| model.alphabet()[t as usize])
            .collect();
        assert_eq!(codec.spell(&[first_rule as u32]).unwrap(), expected);
    }

    #[test]
    fn a_token_outside_the_model_is_an_error() {
        let codec = standard().expect("the embedded tables");
        assert!(matches!(
            codec.spell(&[u32::MAX]),
            Err(Error::Model("a token is outside the model"))
        ));
    }

    /// The definition of `ENCODING.md` §1, written the slow obvious way:
    /// repeatedly merge the lowest-rank adjacent pair, the leftmost of a tie.
    fn naive(tokens: &[u32], plan: &HashMap<(u32, u32), (u32, u32)>) -> Vec<u32> {
        let mut words = tokens.to_vec();
        while let Some((i, new_word)) = words
            .windows(2)
            .enumerate()
            .filter_map(|(i, pair)| plan.get(&(pair[0], pair[1])).map(|&(r, w)| (r, i, w)))
            .min_by_key(|&(rank, i, _)| (rank, i))
            .map(|(_, i, w)| (i, w))
        {
            words[i] = new_word;
            words.remove(i + 1);
        }
        words
    }

    #[test]
    fn the_sweep_agrees_with_the_definition() {
        let codec = standard().expect("the embedded tables");
        let model = codec.model();
        let plan = model.plan();
        let n_words = model.alphabet().len() as u32 + model.rules().len() as u32;
        let mut seed = 0x2545_f491_4f6c_dd1du64;
        let mut roll = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        for _ in 0..20_000 {
            let len = (roll() % 10) as usize;
            let tokens: Vec<u32> = (0..len)
                .map(|_| {
                    let r = roll();
                    let wide = (r / 4) as u32;
                    // Mostly characters, sometimes a longer word, so that the
                    // same pair can turn up in several places at once.
                    if r % 4 == 0 { wide % n_words } else { wide % 64 }
                })
                .collect();
            assert_eq!(
                merge_pairs(tokens.clone(), plan),
                naive(&tokens, plan),
                "{tokens:?}"
            );
        }
    }

    #[test]
    fn a_stale_heap_entry_does_not_merge_early() {
        // "Find".  The pairs are (F,i) rank 92, (i,n) rank 4 and (n,d) rank
        // 998, so the sweep merges (i,n) first.  That changes the pair at
        // position 0 to (F,in) rank 978, but the entry queued there at rank 92
        // is still in the heap; taken at face value it would merge (F,in) long
        // before rank 978, and the (in,d) rule at rank 125 — the merge that
        // leads to the answer — could never then fire.  Reading the rank back
        // out of the plan when an entry surfaces is what prevents this; the
        // random test above only stumbles on such a case by luck of the draw.
        let codec = standard().expect("the embedded tables");
        let model = codec.model();
        let tokens: Vec<u32> = "Find"
            .chars()
            .map(|c| model.char_id(c).expect("a character of the alphabet"))
            .collect();
        assert_eq!(merge_pairs(tokens, model.plan()).len(), 1);
    }
}

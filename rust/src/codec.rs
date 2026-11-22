//! The codec: identifier ↔ bit string ↔ integer (`ENCODING.md` §2).
//!
//! The code alternates two steps: *which right cluster comes next, given the
//! left cluster we are in*, then *which word in that right cluster*.  An
//! identifier starts in left cluster 0 by convention and ends when the top
//! stage reaches its STOP leaf, whose codeword is all zeros — also the padding
//! above the integer, so the end costs nothing and is not stored.

use std::cmp::Ordering;
use std::collections::BinaryHeap;
use std::fmt;
use std::sync::Arc;

use crate::bitio::{Bits, BitReader, BitWriter};
use crate::model::{CharOrRule, Left, LeftLeaf, Model, Rule, Word};
use crate::Error;

/// The identifier terminates after this many words, whatever the bits say.
const MAX_WORDS: usize = 1_000_000;

/// A [`Model`] tied to the encoding loop, shared behind an [`Arc`].
///
/// The field is public because there is nothing to protect: a codec is
/// exactly a shared model, and the tables inside the model are already
/// private.  Cloning a codec costs an `Arc` increment, so the standard tables
/// are parsed once and every codec points at the same copy.
///
/// [`Codec::default`] returns [`standard::standard()`](crate::standard::standard),
/// the standard codec.
#[derive(Clone)]
pub struct Codec(
    /// The model, shared with every codec cloned from this one.
    pub Arc<Model>,
);

impl Codec {
    /// Wrap a model in an [`Arc`] and tie it to the encoding loop.
    pub fn new(model: Model) -> Self {
        Codec(Arc::new(model))
    }

    // ------------------------------------------------------------- encoding

    /// Split an identifier into the model's words (`ENCODING.md` §1).
    pub fn tokenise(&self, identifier: &str) -> Result<Vec<Word>, Error> {
        let mut words = Vec::with_capacity(identifier.len());
        for c in identifier.chars() {
            words.push(
                self.0
                    .char_id(c)
                    .ok_or(Error::UnknownCharacter(c))?
                    .word(),
            );
        }
        Ok(MergePairs::new(&self.0, words).run())
    }

    /// The codeword as a bit string, stream order, trailing zeros cut.
    pub fn encode_bits(&self, identifier: &str) -> Result<Bits, Error> {
        let words = self.tokenise(identifier)?;
        let mut writer = BitWriter::new();
        let mut left = Left(0);
        for word in words {
            let right = self.0.right(word)?;
            self.0
                .top_tree(left)?
                .write(&mut writer, LeftLeaf::from(right))?;
            self.0
                .bottom_tree(right)?
                .write(&mut writer, self.0.position(word)?)?;
            left = self.0.left(word)?;
        }
        self.0.top_tree(left)?.write(&mut writer, LeftLeaf::STOP)?;
        Ok(writer.finish())
    }

    /// The integer code for an identifier.
    ///
    /// The code is the value of the bit string [`Codec::encode_bits`] returns,
    /// so this is the encoding's integer form; use that method when the code
    /// needs more than 128 bits.  Fails with [`Error::CodeTooLong`] when a set
    /// bit lies at index 128 or above.
    pub fn encode(&self, identifier: &str) -> Result<u128, Error> {
        let bits = self.encode_bits(identifier)?;
        bits.to_u128().ok_or(Error::CodeTooLong { bits: bits.len() })
    }

    // ------------------------------------------------------------- decoding

    /// Decode a bit string; bits past the end read as zeros.
    pub fn decode_bits(&self, bits: &Bits) -> Result<String, Error> {
        let mut reader = BitReader::new(bits.as_bytes());
        let mut words = Vec::new();
        let mut left = Left(0);
        for _ in 0..MAX_WORDS {
            let Some(right) = self.0.top_tree(left)?.read(&mut reader)?.right() else {
                return self.spell(&words);
            };
            let position = self.0.bottom_tree(right)?.read(&mut reader)?;
            let word = self.0.word_at(right, position)?;
            words.push(word);
            left = self.0.left(word)?;
        }
        Err(Error::DoesNotTerminate)
    }

    /// Decode an integer code.
    pub fn decode(&self, value: u128) -> Result<String, Error> {
        self.decode_bits(&Bits::from_u128(value))
    }

    /// Words back to characters, expanding only the words that are present.
    ///
    /// A rule names children whose ids are smaller than its own — [`Model`]
    /// rejects any other rule — so expansion is a walk down a finite tree, and
    /// the words of one identifier are all it needs.  The rule list is never
    /// replayed, so the cost follows the output, not the model.
    fn spell(&self, words: &[Word]) -> Result<String, Error> {
        let mut out = String::with_capacity(words.len());
        let mut stack: Vec<Word> = words.iter().rev().copied().collect();
        while let Some(word) = stack.pop() {
            match self.0.parts(word)? {
                CharOrRule::Char(c) => out.push(self.0.char_at(c)?),
                CharOrRule::Rule(rule) => {
                    let (a, b) = self.0.children(rule)?;
                    stack.push(b); // the left operand comes off the stack first
                    stack.push(a);
                }
            }
        }
        Ok(out)
    }
}

/// The codec's shape, not its tables: `Model::info()` describes the model
/// without printing eight thousand words.
impl fmt::Debug for Codec {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Codec({})", self.0.info())
    }
}

/// A live node: a word id and its neighbours in the identifier.
///
/// A merge keeps the left node and removes the right one, so the head of the
/// list is always position 0 and the tail has no `next`.
#[derive(Clone, Copy)]
struct Node {
    word: Word,
    next: Option<usize>,
    prev: Option<usize>,
}

/// A queued merge: the rule and the position it applies at.
///
/// Only the rule orders the heap.  Two occurrences of one rule cannot overlap —
/// a rule's children differ, and the model holds one rule per pair — so merges
/// of equal rank are independent, and the order among them cannot matter.
/// That is why nothing here has to implement "the leftmost of a tie".
///
/// The order is *reversed*: a low rank is the higher priority, and the heap is
/// a max-heap, so `cmp` puts the smaller rule first.
#[derive(Clone, Copy)]
struct Candidate {
    rule: Rule,
    position: usize,
}

impl PartialEq for Candidate {
    fn eq(&self, other: &Self) -> bool {
        self.rule == other.rule
    }
}

impl Eq for Candidate {}

impl PartialOrd for Candidate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Candidate {
    fn cmp(&self, other: &Self) -> Ordering {
        other.rule.cmp(&self.rule)
    }
}

/// The tokeniser of `ENCODING.md` §1, in one pass.
///
/// A linked list over the positions makes each merge a constant amount of work
/// besides the heap; the heap holds one entry per candidate pair, and entries
/// whose pair has since changed are skipped when they surface.
///
/// Ranks are nested — a merge's rank exceeds the ranks that built its operands
/// — so any pair a merge creates has a rank above the one just used, and a
/// sweep that always takes the lowest rank performs the merges in the order the
/// model defines.
struct MergePairs<'a> {
    /// `None` where a node has been merged away.
    nodes: Vec<Option<Node>>,
    model: &'a Model,
    heap: BinaryHeap<Candidate>,
}

impl<'a> MergePairs<'a> {
    /// A sweep over `words`, whose adjacent pairs are looked up in the model.
    fn new(model: &'a Model, words: Vec<Word>) -> Self {
        let n = words.len();
        let nodes = words
            .into_iter()
            .enumerate()
            .map(|(i, word)| {
                Some(Node {
                    word,
                    next: (i + 1 < n).then_some(i + 1),
                    prev: i.checked_sub(1),
                })
            })
            .collect();
        MergePairs {
            nodes,
            model,
            heap: BinaryHeap::new(),
        }
    }

    /// Offer the pair that starts at `i`, if the model has a rule for it.
    fn push(&mut self, i: usize) {
        let Some(Node { word, next: Some(j), .. }) = self.nodes[i] else {
            return;
        };
        let Some(right) = self.nodes[j] else { return };
        if let Some(rule) = self.model.rule_for(word, right.word) {
            self.heap.push(Candidate { rule, position: i });
        }
    }

    /// Merge until no adjacent pair has a rule; return the words that remain.
    fn run(mut self) -> Vec<Word> {
        for i in 0..self.nodes.len().saturating_sub(1) {
            self.push(i);
        }
        while let Some(Candidate { rule, position: i }) = self.heap.pop() {
            // The pair at `i` may have gone, or changed, since it was queued.
            let Some(Node { word, next: Some(j), prev }) = self.nodes[i] else {
                continue;
            };
            let Some(right) = self.nodes[j] else { continue };
            // The entry is still good if the rule we queued still has the
            // words now at `i`.  `rule` came out of `rule_for`, so it exists;
            // comparing its children is one array read, where asking
            // `rule_for` again would hash the pair a second time.
            if self.model.children(rule).ok() != Some((word, right.word)) {
                continue; // stale: the pair at `i` is not the one we queued
            }
            let merged = self.model.word_of_rule(rule);
            let followed = right.next;
            self.nodes[i] = Some(Node {
                word: merged,
                next: followed,
                prev,
            });
            self.nodes[j] = None;
            if let Some(f) = followed {
                if let Some(node) = self.nodes[f].as_mut() {
                    node.prev = Some(i);
                }
            }
            // The pair before `i` is new too, because `i`'s word has changed.
            if let Some(p) = prev {
                self.push(p);
            }
            self.push(i);
        }
        // A merge keeps the left node, so the survivors are still in order.
        self.nodes.iter().flatten().map(|node| node.word).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bitio::{BitReader, BitWriter};
    use crate::model::{Char, RightLeaf};

    #[test]
    fn spelling_is_the_expansion_of_the_words_alone() {
        let codec = Codec::default();
        let model = &codec.0;
        assert_eq!(codec.spell(&[]).unwrap(), "");
        let c = model.char_at(Char(0)).expect("the first character");
        assert_eq!(codec.spell(&[Char(0).word()]).unwrap(), c.to_string());
        // The first rule merges two characters, so spelling its two children
        // and spelling the word it defines must give the same text.
        let (a, b) = model.children(Rule(0)).expect("the first rule");
        let expected = codec.spell(&[a, b]).expect("two characters");
        let rule_word = model.word_of_rule(Rule(0));
        assert_eq!(codec.spell(&[rule_word]).unwrap(), expected);
    }

    #[test]
    fn a_one_word_cluster_codes_in_zero_bits() {
        // A bottom tree with a single leaf has the empty codeword: encoding
        // spends nothing and decoding returns the leaf without touching the
        // stream.  The standard model has such clusters, so this is not a
        // hypothetical shape.
        let codec = Codec::default();
        let model = &codec.0;
        let (word, right) = (0..model.num_words())
            .map(|w| (Word(w), model.right(Word(w)).expect("a word")))
            .find(|&(_, right)| model.bottom_tree(right).unwrap().num_leaves() == 1)
            .expect("the standard model has a cluster with one word");
        let tree = model.bottom_tree(right).expect("a tree");
        let mut writer = BitWriter::new();
        tree.write(&mut writer, RightLeaf(0)).expect("the only leaf");
        assert!(writer.finish().is_empty());
        let mut reader = BitReader::new(&[]);
        assert_eq!(tree.read(&mut reader), Ok(RightLeaf(0)));
        assert_eq!(reader.position(), 0);
        assert_eq!(model.word_at(right, RightLeaf(0)), Ok(word));
    }

    #[test]
    fn a_word_outside_the_model_is_an_error() {
        let codec = Codec::default();
        assert!(matches!(
            codec.spell(&[Word(u32::MAX)]),
            Err(Error::Model("a word is outside the model"))
        ));
    }

    /// The definition of `ENCODING.md` §1, written the slow obvious way:
    /// repeatedly merge the lowest-rank adjacent pair.  The position is used
    /// only to break a tie, which cannot change the result (§5 of `STANDARD.md`).
    fn naive(words: &[Word], model: &Model) -> Vec<Word> {
        let mut out = words.to_vec();
        while let Some((i, rule)) = out
            .windows(2)
            .enumerate()
            .filter_map(|(i, pair)| {
                model
                    .rule_for(pair[0], pair[1])
                    .map(|rule| (rule.0, i, rule))
            })
            .min_by_key(|&(rank, i, _)| (rank, i))
            .map(|(_, i, rule)| (i, rule))
        {
            out[i] = model.word_of_rule(rule);
            out.remove(i + 1);
        }
        out
    }

    #[test]
    fn the_sweep_agrees_with_the_definition() {
        let codec = Codec::default();
        let model = &codec.0;
        let n_words = model.num_words();
        let mut seed = 0x2545_f491_4f6c_dd1du64;
        let mut roll = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        for _ in 0..20_000 {
            let len = (roll() % 10) as usize;
            let words: Vec<Word> = (0..len)
                .map(|_| {
                    let r = roll();
                    let wide = (r / 4) as u32;
                    // Mostly characters, sometimes a longer word, so that the
                    // same pair can turn up in several places at once.
                    Word(if r % 4 == 0 { wide % n_words } else { wide % 64 })
                })
                .collect();
            assert_eq!(
                MergePairs::new(model, words.clone()).run(),
                naive(&words, model),
                "{words:?}"
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
        // leads to the answer — could never then fire.  Comparing the queued
        // rank's children with the words now at the position, when the entry
        // surfaces, is what prevents this; the random test above only stumbles
        // on such a case by luck of the draw.
        let codec = Codec::default();
        let model = &codec.0;
        let words: Vec<Word> = "Find"
            .chars()
            .map(|c| model.char_id(c).expect("a character of the alphabet").word())
            .collect();
        assert_eq!(MergePairs::new(model, words).run().len(), 1);
    }
}

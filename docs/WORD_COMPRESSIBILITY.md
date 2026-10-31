# Word-level (dictionary) compressibility of identifiers

This note applies the **run-aware dictionary model** of
[`TREE_WORDS.md`](TREE_WORDS.md) to estimate the ideal compressed size of
identifiers, in the same style as the character-level study
[`CODE_LENGTHS.md`](CODE_LENGTHS.md), so the two can be compared.

No bit-packing is proposed: the numbers are *rate* estimates (ideal arithmetic
code lengths under the model).  Identifiers that do not fit a budget fall back to
a hash + global-dictionary scheme and are counted as failures, exactly as in
`CODE_LENGTHS.md`.

## The model

1. **Dictionary.**  Build the word list by the greedy **run-aware** rule of
   `TREE_WORDS.md` §9.1 on the **training** corpus: start from the single
   characters, then create `NUM_PAIRS` *words* in total — find the most common
   length-2 substring `uv` of words; if `u ≠ v` merge it (ordinary BPE, one
   word); if `u = v` **collapse every maximal run `u^k` (`k ≥ 2`) to a flat word
   `(u^k)`**, one word per observed run length (a `k`-ary node, *not* `k−1`
   nested merges), so a run step may spend several words of the budget at once.
   The stop character `\n` is a **separator**, never merged across (a word
   spanning two identifiers is meaningless).

2. **Tokenise.**  An identifier is tokenised by replaying the word list in
   creation order: consecutive pair rules are applied by repeatedly merging the
   *lowest-ranked* adjacent pair, and a run rule replaces each maximal run `u^k`
   by `(u^k)` if that word exists, else by a greedy longest-match decomposition.
   This is a *dictionary split*: only word boundaries matter, the characters
   inside a word are not looked at.

3. **Bigram model.**  The tokenised identifier is treated as the cycle
   `tokens + [\n]` (every identifier has exactly one `\n`).  The model is the
   first-order Markov model over words,

   ```
   P(u_0 ... u_n) = prod_i P(u_{i+1} | u_i),   u_{n+1} = u_0 = \n,
   ```

   with the training adjacency counts `N(u,v)` and the counting prior of
   [`ADJACENCY_MATRIX.md`](ADJACENCY_MATRIX.md) §6 filling unobserved cells:

   ```
   P_ref(v | u) = [ N(u,v) + alpha*(r_u/T)*(c_v/T) ] / [ r_u*(1 + alpha/T) ],
   alpha = kappa * V,
   ```

   where `r_u = sum_v N(u,v) = N(u)`, `c_v = sum_u N(u,v) = N(v)` (the matrix is
   cyclic, so rows and columns both sum to the unigram counts), `T = sum N(u,v)`
   and `V` is the vocabulary size.

4. **Code length.**  `L(id) = sum_i -log2 P_ref(u_{i+1} | u_i)` over the cycle.
   The dictionary and the counts are shared, so they cost nothing per string.
   The **success rate** at budget `B` is the fraction of held-out *distinct*
   identifiers with `L(id) <= B`.

> This is the **run-aware** rule.  The previous version of this note used a
> plain pair-merge dictionary that built a run `u^k` out of *nested* words
> `(uu)`, `((uu)u)`, … ; `TREE_WORDS.md` §9.1 and the run-word/boundary-word
> experiments in `DICTIONARY_RULES.md` show
> the flat `(u^k)` rule is preferable (it beats plain BPE whenever there is run
> mass and is the sign-safe rule), so all numbers here were regenerated on it.
> Those plain-pair artifacts are obsolete and live only in git history.

## Setup

* Training corpus `work/camel/merged_training.txt` (2,065,806 identifiers),
  validation `work/camel/merged_validation.txt` (229,534) — a deterministic
  9:1 interleaved split (`scripts/split_corpus.py`).
* Dictionary built on a 5% stride sample of the training corpus (103,291
  identifiers); counts and scoring use the full training / validation corpora.
* `NUM_PAIRS` is chosen so the vocabulary `V = 63 characters + 1 stop +
  NUM_PAIRS` matches the context count of a `CODE_LENGTHS.md` threshold `T`.

## Results

Word-level model (held-out validation, `kappa = 1000`):

| `NUM_PAIRS` | vocab `V` | distinct word bigrams | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|
| 96 | 160 | 20,499 | 64.86 | 60.7% | 95.2% |
| 512 | 576 | 149,932 | 54.05 | 74.1% | 97.9% |
| 2,040 | 2,104 | 802,606 | 45.79 | 85.0% | 99.2% |

Character-level model (`CODE_LENGTHS.md`, same corpus), at the nearest
vocabulary sizes:

| `T` | contexts | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|
| 100000 | 159 | 71.45 | 52.3% | 92.8% |
| 20000 | 911 | 60.17 | 66.4% | 96.5% |
| 10000 | 2,102 | 55.19 | 72.6% | 97.6% |

## What it shows

* **At a small dictionary the two models are close** (vocab ≈ 160: 64.9 vs
  71.5 mean bits, 60.7% vs 52.3% in 64 bits) — the word model is already ahead.
* **At equal dictionary size the word model now wins, and the gap grows with
  the dictionary.**  At vocab ≈ 576 the word model needs 54.1 bits against an
  interpolated ≈ 63 for the character model (between its 159-context 71.5 and
  911-context 60.2 points) and fits 74.1% against ≈ 63% in 64 bits; at
  vocab ≈ 2,100 it needs 45.8 bits against 55.2 and fits 85.0% against 72.6%.
* Plausibly the reason is that an identifier is a *sequence of morphemes*
  (`get`, `User`, `Count`, `ion`, …): a word bigram table spends one bigram per
  morpheme boundary where the character model spends a variable-order suffix
  context per character.  Once the dictionary holds the common morphemes, the
  word model captures the short-range morpheme-to-morpheme dependence directly —
  and the run-aware rule (flat `(u^k)` words) keeps runs of repeated characters
  cheap (e.g. `ss`, `tt`, `---`) instead of paying for them character by
  character.
* This is a fair comparison of *models at a dictionary size*, not of *orders*:
  the word model is a first-order word Markov model, the character model is an
  effectively unbounded-order character model.  Neither buys any context
  machinery beyond its table.
* The word model needs no variable-order context machinery — only a word list
  and one bigram table — and is now the better rate estimator at every tested
  size.

## kappa for the word matrix

The word bigram matrix is **denser** than the character context matrix, so it
needs less prior.  On the `NUM_PAIRS = 2040` model (a stride-3 held-out sample,
76,512 identifiers, so a larger absolute rate than the full-table above), the
held-out fit is optimised near `kappa ≈ 100–300` and degrades at both ends:

| `kappa` | 3 | 10 | 30 | 100 | 300 | 1000 | 3000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| mean bits | 46.31 | 46.08 | 45.88 | 45.69 | 45.60 | 45.80 | 46.72 |
| fit ≤64 | 84.2% | 84.5% | 84.8% | 85.0% | 85.1% | 84.9% | 83.9% |

`kappa = 0` diverges (unseen bigrams unrepresentable).  A `kappa ≈ 100–300`
would be the word-matrix analogue of the character default (`ADJACENCY_MATRIX.md`
uses 1000); the difference is only ~0.2 bit, so the main table uses `kappa =
1000` to share one setting with the character study.

## Reproducing

```sh
python3 scripts/split_corpus.py                     # train / validation split
python3 scripts/tree_words.py train \
    --corpus work/camel/merged_training.txt \
    --num-pairs 2040 --sample 20 --jobs 4 --outdir work/tw2040
python3 scripts/tree_words.py score \
    --dir work/tw2040 --corpus work/camel/merged_validation.txt --kappa 1000
```

`work/tw96`, `work/tw512`, `work/tw2040` hold the three dictionaries and their
adjacency matrices (`adj.npz`: `rows`, `cols`, `data`, `uni`, `nvoc`;
`dict.txt` / `sym.npy`: the word list).  `dict.txt` starts with the character
set on its first line, then records each rule on its own line — `P a b` for a
pair merge, `R a k1 k2 …` for a run rule that created the words
`(a^k1), (a^k2), …`.

`scripts/check_tree_words.py` is the regression test for the dictionary and
tokeniser (builder against a from-scratch recount, fast plan replay against an
independent replay, incremental bigrams against a direct count):
`python3 scripts/check_tree_words.py --real`.

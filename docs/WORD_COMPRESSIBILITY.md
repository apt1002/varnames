# Word-level (dictionary) compressibility of identifiers

This note applies the **pair-merge dictionary model** of
[`TREE_WORDS.md`](TREE_WORDS.md) to estimate the ideal compressed size of
identifiers, in the same style as the character-level study
[`CODE_LENGTHS.md`](CODE_LENGTHS.md), so the two can be compared.

No bit-packing is proposed: the numbers are *rate* estimates (ideal arithmetic
code lengths under the model).  Identifiers that do not fit a budget fall back to
a hash + global-dictionary scheme and are counted as failures, exactly as in
`CODE_LENGTHS.md`.

## The model

1. **Dictionary.**  Build the word list by the greedy **most-frequent-pair**
   rule of `TREE_WORDS.md` §2 on the **training** corpus: start from the single
   characters plus the stop character `\n`, then create `NUM_PAIRS` words,
   always merging the most common length-2 substring `uv` of *words*.  A merge
   of a word with itself is **forbidden**, so no `uu` word is ever built and a
   doubled character enters the vocabulary only inside a pair word that also
   contains a neighbour (`sse`, `ess`, `tte`, `__i`).  The stop character is a
   **separator**, never merged across (a word spanning two identifiers is
   meaningless).
   *(History: an earlier rule collapsed every maximal run `u^k` into one word per
   observed length.  `DICTIONARY_RULES.md` measures that dropping it changes the
   held-out mean by at most 0.02 bits at the vocabularies in use; the run path has
   since been deleted from `scripts/tree_words.py`, so that comparison is a
   record rather than a live one.)*

2. **Tokenise.**  An identifier is tokenised by replaying the word list in
   creation order: repeatedly merge the *lowest-ranked* adjacent pair.  This is a
   *dictionary split*: only word boundaries matter, the characters inside a word
   are not looked at.

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

## Setup

* Training corpus `work/camel/merged_training.txt` (3,804,036 identifiers),
  validation `work/camel/merged_validation.txt` (422,671) — a deterministic
  9:1 interleaved split (`scripts/split_corpus.py`).
* Dictionary built on a 5% stride sample of the training corpus (190,202
  identifiers); counts and scoring use the full training / validation corpora.
* `V` is `63 characters + 1 stop + NUM_PAIRS`; the grid is `V = 4,096`, `6,144`,
  `8,192`, chosen to match the context count of a `CODE_LENGTHS.md` threshold
  `T`.
* Held-out scoring on a stride-10 sample of the validation set
  (`n = 42,268`), `kappa = 300` — the canonical prior, and the measured optimum
  (see "kappa for the word matrix" below).

## Results

Word-level model:

| vocab `V` | words | distinct word bigrams | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 4,032 | 1,813,165 | 42.15 | 90.3% | 99.5% |
| 6,144 | 6,080 | 2,237,618 | 40.79 | 92.0% | 99.6% |
| 8,192 | 8,128 | 2,507,680 | 39.95 | 93.1% | 99.7% |

Building the dictionaries on the full corpus (`--sample 0`) instead of the 5%
sample barely moves the score and has no systematic sign — `V = 4,096`: 42.16
bits, 90.3% / 99.5% (vs 42.15 / 90.3% / 99.5%); `V = 8,192`: 39.94, 93.1% /
99.7% — so the 5% sample is an adequate proxy for ranking merges, and the table
above is robust to it.

Character-level model (`CODE_LENGTHS.md`, same corpus), at the nearest
dictionary sizes:

| `T` | contexts | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|
| 100000 | 278 | 65.53 | 60.0% | 95.0% |
| 20000 | 1,788 | 54.63 | 74.3% | 97.7% |
| 10000 | 3,935 | 50.75 | 79.1% | 98.4% |
| 5000 | 8,038 | 47.64 | 82.8% | 98.9% |
| 2000 | 20,198 | 44.42 | 86.8% | 99.3% |

## What it shows

* **At equal dictionary size the word model wins throughout, by 7–9 bits and
  ~10–11 points of 64-bit fit.**  At `V = 4,096` (4,032 words against 3,935
  contexts at `T = 10,000`) the word model needs 42.15 bits where the character
  model needs 50.75 and fits 90.3% against 79.1% in 64 bits; at `V = 8,192`
  (8,128 words against 8,038 contexts at `T = 5,000`) 39.95 against 47.64 and
  93.1% against 82.8%; `V = 6,144` sits between the two character points
  (40.79 against 47.6–50.8).
* **The word list keeps paying, with diminishing returns, and the gains are
  concentrated at the 64-bit budget.**  From `V = 4,096` to `6,144` the word
  model drops 1.36 bits and the 64-bit fit rises 1.7 points; the next 2,048 words
  buy another 0.84 bits and 1.1 points.  Meanwhile the 128-bit fit is nearly
  saturated (99.5% → 99.7%), so a larger word list mostly rescues identifiers
  that were just over the 64-bit line.  This is the "buy words first" result of
  [`CLUSTER_WORDS.md`](CLUSTER_WORDS.md), seen from the fit-rate side.
* Plausibly the reason is that an identifier is a *sequence of morphemes*
  (`get`, `User`, `Count`, `ion`, …): a word bigram table spends one bigram per
  morpheme boundary where the character model spends a variable-order suffix
  context per character.  Once the dictionary holds the common morphemes, the
  word model captures the short-range morpheme-to-morpheme dependence directly.
* This is a fair comparison of *models at a dictionary size*, not of *orders*:
  the word model is a first-order word Markov model, the character model is an
  effectively unbounded-order character model.  Neither buys any context
  machinery beyond its table.
* The word model needs no variable-order context machinery — only a word list
  and one bigram table — and is now the better rate estimator at every tested
  size.

## kappa for the word matrix

The word bigram matrix is **denser** than the character context matrix, so it
might need less prior.  Swept on the full-table model at stride 10
(`n = 42,268`):

| `kappa` | 3 | 10 | 30 | 100 | **300** | 1000 | 3000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `V = 4,096`, mean bits | 43.30 | 42.95 | 42.64 | 42.33 | **42.15** | 42.27 | 43.11 |
| `V = 4,096`, fit ≤64 | 89.2% | 89.6% | 89.9% | 90.2% | **90.3%** | 90.2% | 89.3% |
| `V = 8,192`, mean bits | 41.75 | 41.17 | 40.66 | 40.18 | **39.95** | 40.31 | 41.63 |
| `V = 8,192`, fit ≤64 | 91.5% | 92.1% | 92.6% | 92.9% | **93.1%** | 92.7% | 91.5% |

The optimum is `kappa = 300` at both ends of the grid — the same value the
character prior uses — and the curve is flat within 0.2 bit between 100 and 300.
`kappa = 0` diverges (unseen bigrams unrepresentable).  Larger `kappa` costs
more at the top of the grid, because the prior's mass `kappa·V` grows with `V`
against a shrinking token total: at `V = 8,192`, `alpha = 300·V` is 12.8% of
`T`, against 5.7% at `V = 4,096`.

## Reproducing

```sh
python3 scripts/split_corpus.py                     # train / validation split
sh scripts/h5_build.sh ns                           # the whole grid, 5% sample
# or one vocabulary: --sample 20, --stride 0 (all lines), --jobs $(nproc)
python3 scripts/tree_words.py train \
    --corpus work/camel/merged_training.txt \
    --num-pairs 4032 --sample 20 --stride 0 --jobs 4 --outdir work/tw4096ns
python3 scripts/model_fit_rates.py --dir work/tw4096ns --ks 16 --kappa 300 \
    --stride 10
```

Two caveats on the grid builds:

* **Dead words.**  A few dictionary entries never appear in the final
  tokenisation (1 at `V = 4,096`, 4 at `6,144`, 16 at `8,192`; the `--sample 0`
  twins give 1 and 9): they are merge steps that are *always absorbed* into a
  longer word, so they exist only as intermediate nodes (e.g. `olean`, which only
  ever occurs inside `Boolean`/`boolean`), or their boundary is pre-empted by a
  lower-ranked merge.  Their unigram count is zero, which would divide by zero in
  the scoring; the scorer floors them at 0.5 (Laplace) so their row and prior
  mass are defined.  They are intrinsic to the greedy merge, not a sampling
  artifact.
* **Cost.**  On the 4-core box the grid builds in 33 s / 61 s / 77 s for
  `V = 4,096` / `6,144` / `8,192` (5% dictionary sample, full adjacency), and
  scoring the stride-10 sample takes ~1–4 minutes per vocabulary.

`work/tw<V>ns/` holds the dictionary and matrix: `dict.txt` starts with the
character set on its first line, then records each rule on its own line — `P a b`
for a pair merge (the only rule type since the run rule was removed); `sym.npy`
is the symbol table; `adj.npz` holds the adjacency triplets (`rows`, `cols`,
`data`), the unigram counts (`uni`) and `nvoc`; `meta.json` records the corpus,
`num_pairs`, `sample` and the dictionary-sample line count.  The `s0` twins are
the same build with `--sample 0`.  The directory key is in `PLAN.md`.

`scripts/check_tree_words.py` is the regression test for the dictionary and
tokeniser (builder against a from-scratch recount, fast plan replay against an
independent replay, incremental bigrams against a direct count):
`python3 scripts/check_tree_words.py --real`.

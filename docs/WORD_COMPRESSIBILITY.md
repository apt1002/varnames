# Word-level (dictionary) compressibility of identifiers

This note applies the pair-merge **dictionary model** of
[`TREE_WORDS.md`](TREE_WORDS.md) to estimate the ideal compressed size of
identifiers, in the same style as the character-level study
[`CODE_LENGTHS.md`](CODE_LENGTHS.md), so the two can be compared.

No bit-packing is proposed: the numbers are *rate* estimates (ideal arithmetic
code lengths under the model).  Identifiers that do not fit a budget fall back to
a hash + global-dictionary scheme and are counted as failures, exactly as in
`CODE_LENGTHS.md`.

## The model

1. **Dictionary.**  Build the word list by the greedy pair-merge rule of
   `TREE_WORDS.md` on the **training** corpus: start from the single characters,
   then `NUM_PAIRS` times find the most common length-2 substring `uv` of words
   and replace every occurrence of `uv` by the new word `(uv)`.  The stop
   character `\n` is a **separator**, never merged across (a word spanning two
   identifiers is meaningless), and occurrences are replaced left-to-right,
   non-overlapping (so runs such as `uuu` are not a special case).

2. **Tokenise.**  An identifier is tokenised by replaying the word list in
   creation order, i.e. by repeatedly merging its lowest-ranked adjacent pair.
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
| 96 | 160 | 5,972 | 73.24 | 50.1% | 92.1% |
| 512 | 576 | 12,598 | 68.80 | 55.8% | 93.8% |
| 2,040 | 2,104 | 39,491 | 63.95 | 61.7% | 95.6% |

Character-level model (`CODE_LENGTHS.md`, same corpus), at the nearest
vocabulary sizes:

| `T` | contexts | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|
| 100000 | 159 | 71.45 | 52.3% | 92.8% |
| 20000 | 911 | 60.17 | 66.4% | 96.5% |
| 10000 | 2,102 | 55.19 | 72.6% | 97.6% |

## What it shows

* **At a small dictionary the two models are close** (vocab ≈ 160: 73.2 vs
  71.5 mean bits, 50.1% vs 52.3% in 64 bits).
* **At equal dictionary size the character model pulls ahead sharply.**  At
  vocab ≈ 2,100 the word model needs 63.9 bits against the character model's
  55.2, and fits 61.7% against 72.6% in 64 bits.  The gap grows with the
  dictionary: the word model adds a word at a time and pays for each word with a
  single bigram factor, whereas the character model spends its contexts on
  *variable-order suffix* contexts and can look several characters back.
* This is a fair comparison of *models at a dictionary size*, not of *orders*:
  the word model is a first-order word Markov model, the character model is an
  effectively unbounded-order character model.  The pair-merge dictionary is
  also greedy by frequency, not by code length, so its words are good for
  *counting*, not chosen to minimise bits.
* The word model still buys real compression over the char model's crude end of
  its range, and needs no variable-order context machinery — only a word list
  and one bigram table.

## kappa for the word matrix

`kappa = 1000` (the `ADJACENCY_MATRIX.md` default, tuned on the character
context matrices) is **conservative** here.  On the `NUM_PAIRS = 2040` model the
held-out fit is essentially flat for `kappa` in `3 … 300` and only degrades past
`1000`:

| `kappa` | 0 | 3 | 10 | 30 | 100 | 300 | 1000 | 3000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mean bits | ∞ | 63.74 | 63.74 | 63.74 | 63.75 | 63.80 | 64.07 | 64.97 |
| fit ≤64 | 61.3% | 61.5% | 61.5% | 61.5% | 61.5% | 61.4% | 61.0% | 59.9% |

`kappa = 0` diverges (unseen bigrams unrepresentable).  The word bigram matrix
is *denser* than the character context matrix, so it needs less prior; a
`kappa ≈ 30–100` would be the word-matrix analogue of the character default.
The table above uses `kappa = 1000` so the two studies share one setting; the
qualitative gap to `CODE_LENGTHS.md` is insensitive to this choice (a fraction
of a bit).

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
`dict.txt` / `sym.npy`: the word list).

# The identifier-boundary trigram (`u v \n`)

Status: **negative.**  The pair-merge dictionary never merges across the string
boundary, so a tokenised identifier ends `… u v \n` and the first-order model
codes that boundary with the two **bigrams** `P(v|u)` and `P(\n|v)`.  The
**trigram** `P(\n | u, v)` — "is `v` final, *given* `u`?" — is left on the
table.  A word `v\n` would capture it, but the held-out gain is only
**≈0.4–0.5 bits/string, about 1 % of the compressed size**, and that is an
*upper bound* (any `v\n` word can at most reproduce the full second-order
boundary model).  Not worth the design cost.

## What is on the table

The model bends each identifier `t₀ … t_{k−1}` together with the stop into the
cycle `t₀ … t_{k−1} \n` and charges `−log₂ P(next | current)` per edge.  The
last two content bigrams, `(u,v)` and `(v,\n)`, are coded independently; the
3-way statistic `(u,v,\n)` is not used.

There are two ways to make a word cover two of the three and so capture the
trigram:

* a word `uv` — but a specific `uv` is usually not common enough to survive the
  budget, and it occurs *medially* too, so it says nothing about finality;
* a word `v\n` — this is the sharp route: the boundary bigram `(v,\n)` is one
  of the most frequent in the matrix, and `v\n` as a token makes the transition
  `P(v\n | u) = P(v|u)·P(\n | u,v)` carry exactly the missing trigram.

The bits a `v\n` word can recover are therefore the uncaptured conditional
mutual information, summed over boundaries:

    gain = Σ_{u,v} N(u,v,\n) · log₂[ P(\n | u,v) / P(\n | v) ]
         = Σ_{u,v} N(u,v,\n) · log₂[ N(u,v,\n)·N(v) / (N(u,v)·N(v,\n)) ]
         = N_triples · I(u ; \n | v) ,

where `N(u,v,\n)` counts identifiers whose last two tokens are `u, v`.  `gain`
is non-negative by construction.

## Measurement

`scripts/boundary_trigram.py` tokenises the corpus once with the dictionary of
the directory it is given, accumulates `N(u,v,\n)`, and reports `gain` two ways:

* **in-sample** — plug-in over the whole corpus.  This is optimistic (the
  trigram is fit on the data it is scored on);
* **held-out** — the trigram is counted on a train half and the code length is
  measured on the disjoint test half, backing off to `P(\n|v)` whenever the
  trigram `(u,v,\n)` is unseen.  This is the honest number and also quantifies
  the "unobserved data" wrinkle.

Both are reported against the corpus size `CS = S1 − S2` in bits (the values
below are the unsmoothed MLE corpus size; `WORD_COMPRESSIBILITY.md` quotes
slightly larger κ-smoothed bits/string).

## Results

The whole training corpus `work/camel/merged_training.txt` (3,804,036
identifiers), split in half (1,902,018 train / 1,902,018 test):

| dictionary | `V` | CS (bits/string) | in-sample | held-out | as % of CS | trigram coverage |
|---|---:|---:|---:|---:|---:|---:|
| `tw4096ns` | 4096 | 40.535 | 0.769 | **0.464** | 1.14 % | 72.1 % |
| `tw8192ns` | 8192 | 37.332 | 0.833 | **0.388** | 1.04 % | 58.2 % |

The held-out gain is stable across vocabulary size (0.46 and 0.39 bits/string,
~1 % of the compressed size) and is the same order as the ~1 bit spanned by the
`κ` sweep in `WORD_COMPRESSIBILITY.md` — and an order of magnitude below the
2.3 bits/string won by going from `V = 4096` to `8192`.

## The unobserved-data wrinkle

The in-sample → held-out drop is steep here: 0.77 → 0.46 at `V = 4096` and
0.83 → 0.39 at `V = 8192` (40 % and 53 % of the apparent gain).  The reason is
coverage: only **72 %** (at 4096) and **58 %** (at 8192) of held-out identifiers
end in a `(u,v,\n)` pattern seen in training, so a backoff estimator has to give
up the trigram on the rest.  A larger vocabulary makes words longer and the
last-two-token triples rarer, which is why coverage falls with `V`.

This is not a case where the apparent gain evaporates: ~0.4 bits/string is a
real held-out effect, just a small one.

## Interpretation

The boundary trigram is worth **≈1 %, and strictly less in practice**:

* it is an **upper bound** — a `v\n` word re-expresses `P(v|u)·P(\n|u,v)` as
  `P(v\n|u)`, so it can at best match the full second-order boundary model, not
  beat it;
* realising it costs dictionary slots (competing with ordinary merges) and
  perturbs the surrounding counts, so the realised gain would be smaller;
* it is not a free change to the model.  Absorbing the stop into `w = (v\n)`
  makes `w` the cycle connector, so the string-start term becomes `P(u₀ | w)`
  instead of a fixed `P(u₀ | \n)` — non-causal unless you marginalise the start
  distribution over the terminators — and it breaks the exact `CS = S1 − S2`
  identity of [`TREE_WORDS.md`](TREE_WORDS.md) §10, which relies on the stop
  being a single shared cyclic node.

Weighed against ~1 %, these costs are not worth paying.  Boundary words are
recorded here so the negative is on the books; the simpler design (the stop is
not part of any word) is kept.

## Pre-expansion record

The measurement that established the negative was taken on the 2,065,806-
identifier corpus with the legacy vocabularies `tw512` (CS 53.841) and `tw2040`
(CS 44.481): in-sample 0.608 / 0.725 bits/string, held-out **0.553 / 0.506**
(1.03 % / 1.14 % of CS) with trigram coverage 97.3 % / 81.0 %.  Coverage fell
with `V` there too; the grid simply continues the trend.

## Reproduce

    python3 scripts/boundary_trigram.py --dirs work/tw4096ns work/tw8192ns --jobs 2 --stride 1
    # tokenisation alone is ~2.5 min/dictionary on 4 cores (138 s at V=4096,
    # 148 s at V=8192) over the full 3.8M-line training corpus; --stride N and
    # --jobs J for a quick/large run

(`--dirs` takes a space-separated list.  The in-sample and held-out estimates
are self-consistent at any `--stride` because every count is taken from the
same sampled lines; the numbers above are `--stride 1`.)

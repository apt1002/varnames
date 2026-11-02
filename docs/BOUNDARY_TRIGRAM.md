# The identifier-boundary trigram (`u v \n`)

Status: **negative.**  The run-aware word dictionary never merges across the
string boundary, so a tokenised identifier ends `… u v \n` and the first-order
model codes that boundary with the two **bigrams** `P(v|u)` and `P(\n|v)`.  The
**trigram** `P(\n | u, v)` — "is `v` final, *given* `u`?" — is left on the
table.  A word `v\n` would capture it, but the held-out gain is only
**≈0.5 bits/string, about 1 % of the compressed size**, and that is an *upper
bound* (any `v\n` word can at most reproduce the full second-order boundary
model).  Not worth the design cost.

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

`scripts/boundary_trigram.py` tokenises the corpus once with the run-aware
dictionary and accumulates `N(u,v,\n)`, then reports `gain` two ways:

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

Full corpus `work/camel/merged_training.txt` (2,065,806 identifiers), train/test
split in half:

| dictionary | `V` | CS (bits/string) | in-sample | held-out | as % of CS | trigram coverage |
|---|---:|---:|---:|---:|---:|---:|
| `tw512` | 576 | 53.841 | 0.608 | **0.553** | 1.03 % | 97.3 % |
| `tw2040` | 2104 | 44.481 | 0.725 | **0.506** | 1.14 % | 81.0 % |

The held-out gain is remarkably stable across vocabulary size (0.55 and 0.51
bits/string) and is the same order as the ~1 bit spanned by the `κ` sweep in
`WORD_COMPRESSIBILITY.md` — and an order of magnitude below the ~9 bits/string
won by going from `tw512` to `tw2040`.

## The unobserved-data wrinkle

The in-sample → held-out drop (0.73 → 0.51 at `tw2040`, 0.61 → 0.55 at `tw512`)
is only 8–30 %.  It is small because **81–97 % of held-out identifiers** land on
a `(u,v,\n)` pattern seen in training, so a backoff estimator can actually use
the trigram most of the time.  This is *not* a case where the apparent gain
evaporates once you refuse to score the data you fit: the ≈0.5 bits/string is a
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

## Reproduce

    python3 scripts/boundary_trigram.py --dirs work/tw512 work/tw2040
    # ~5–7 min per dictionary on 4 cores; --stride N and --jobs J for a quick/large run

(The in-sample and held-out estimates are self-consistent at any `--stride`
because every count is taken from the same sampled lines; the full-corpus
numbers above are `--stride 1`.)

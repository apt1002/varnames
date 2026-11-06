# Fixed-budget compressibility of identifiers

This note estimates how many identifiers can be represented in a fixed budget
(say **64 bits** or **128 bits**) by a statistical model of identifiers: the
ideal arithmetic-code length of an identifier under the model, and the fraction
of distinct identifiers whose length fits the budget.

No concrete bit-packing is proposed here; the aim is a *rate* estimate.
Identifiers that do not fit fall back to a hash + global-dictionary scheme, so
they are counted as failures.

## The model

Case-normalise the corpus to CamelCase (see `docs/CASE_NORMALISATION.md`), wrap
each identifier as `^identifier$`, and enumerate the **common substrings** —
substrings of the wrapped identifiers occurring at least *T* times — for a
threshold *T*. The model is the **longest-suffix (variable-order) successor
model**: at each split of `^identifier$` the next character is predicted by the
longest common substring that is a *suffix* of the prefix, e.g. after `^Ac` the
successor is credited to `^Ac` rather than to `Ac` or `c`. Sparse contexts are
smoothed toward the global successor marginal `q` with a Dirichlet prior
(`alpha = 1`):

```
p(c | ctx) = (n_{ctx,c} + alpha * q_c) / (n_ctx + alpha).
```

`scripts/code_lengths.py` computes, for every identifier, the ideal arithmetic
code length

```
L(id) = sum_j  -log2 P(c_j | longest common substring that is a suffix of
                              ^ c_1 ... c_{j-1})
```

which is the number of bits a coder based on the model would spend. The
**static success rate** is the percentage of distinct identifiers in
`work/camel/merged.txt` (4,226,707 after normalisation) with `L(id) <= budget`.

## Results: success rate vs threshold

| T | common substrings | max len | mean bits | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|
| 100000 | 278 | 5 | 65.53 | 60.0% | 95.0% |
| 50000 | 613 | 6 | 60.96 | 66.1% | 96.3% |
| 20000 | 1,788 | 9 | 54.63 | 74.3% | 97.7% |
| 10000 | 3,935 | 13 | 50.75 | 79.1% | 98.4% |
| 5000 | 8,038 | 14 | 47.64 | 82.8% | 98.9% |
| 2000 | 20,198 | 15 | 44.42 | 86.8% | 99.3% |
| 1000 | 40,168 | 30 | 42.61 | 89.0% | 99.5% |
| 500 | 80,869 | 44 | 40.95 | 91.1% | 99.6% |

Observations:

* **More contexts keep helping, with diminishing returns.** Each halving of the
  threshold buys a few more points of static coverage; 500→100000 spans
  91.1%→60.0%. The gain is concentrated in the *long tail*: the common, short
  identifiers are already cheap at every threshold.
* **A 128-bit budget captures almost everything** (95.0% at the crudest model,
  99.6% at the finest). The 64-bit budget is the interesting, discriminating
  regime; 128 bits is effectively "all but the generated long tail".
* These are *model-based* numbers. A real coder also needs to spend bits on
  choosing the model, on the fact that the model is fixed, and so on; treat them
  as an upper bound on the achievable rate.

## The 64-bit threshold in real source code

An earlier study (since retired) weighted each identifier by how often it occurs
in sampled source code, to get an occurrence-weighted ("dynamic") success rate.
It found that the **64-bit threshold accounted for about 92% of identifier
occurrences in source code**, and that this proportion was **relatively
insensitive to improvements in compression**: because occurrences are dominated
by short, highly predictable names, sharpening the model moved the static rate
by tens of points but the occurrence-weighted rate only by a point or two. That
qualitative finding is the useful one and is what we retain; the machinery that
produced it (occurrence sampling + case-normalised counts) has been removed. It
would be easy to reproduce in future if the exact curve is ever wanted.

## Reproducing

```sh
# case-normalise the corpus and build the common substrings (some threshold T)
sh scripts/run_camel_pipeline.sh corpus/identifiers.multilang.txt work/camel
python3 scripts/common_substrings.py work/camel/merged.txt \
        --outdir work/common10000 --threshold 10000
# successor distributions and per-identifier code lengths
python3 scripts/successor_distributions.py work/camel/merged.txt \
        work/common10000/common_substrings.txt --outdir work/common10000
python3 scripts/code_lengths.py work/camel/merged.txt \
        work/common10000/common_substrings.txt --outdir work/common10000
# code_lengths.tsv holds one row per identifier: id, bits
```

`scripts/run_sweep.sh` runs this over a list of thresholds.

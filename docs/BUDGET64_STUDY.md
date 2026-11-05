# The 64-bit and 128-bit identifier sets

Status: **results (partial — the two larger vocabularies are pending).**  What
fraction of real identifiers do the fixed budgets cover, where the boundary
lies in *character* length, and what a random member of the set looks like.
Run against models that actually fit the byte budget
([`MODEL_BUDGET.md`](MODEL_BUDGET.md)), not against the full table.

## Setup

`scripts/budget64_study.py`, model `V = 2,104` (`work/tw2040`), `kappa = 300`,
held-out validation at stride 10 (`n = 22,954` distinct identifiers).  The
`assoc` transition is evaluated from the stored numbers `(c, D)`; `k = 52` is
the 16.7 kB model and `k = 105` the 24.8 kB one.

## 1. Coverage

| model | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|
| full table (4.2 MB) | 45.61 | 85.3 % | 99.2 % |
| `k = 52` (16.7 kB) | 56.37 | 71.3 % | 97.1 % |
| `k = 105` (24.8 kB) | 55.14 | 72.6 % | 97.4 % |

The 64-bit set is the discriminating one; the 128-bit set is close to
"everything except the generated long tail".  Clustering costs ~13 points of
64-bit coverage against the full table — far more than the ~1 bit of mean it
costs — so the budget question (how big a table we can afford) is really a
64-bit-coverage question.

The occurrence-weighted view is not measured here (the source-code occurrence
sampler was retired, see [`CODE_LENGTHS.md`](CODE_LENGTHS.md)); that earlier
study found the 64-bit threshold covered ~92 % of identifier *occurrences* and
was insensitive to model sharpening, because occurrences are dominated by
short, predictable names.  The static rate above is the pessimistic end.

## 2. The boundary in uncompressed length

Code length is **not** monotone in character length, so there is no clean length
cut — only an overlap:

* the **longest identifier that still fits** is **42 characters**;
* the **shortest identifier that fails** is **8 characters**;
* **6,027 identifiers shorter than 42 characters still fail** (of 6,590 total
  failures) — i.e. ~91 % of the failures are *inside* the fitting length range.

Fit rate by character length (`k = 52`):

| len | n | fit ≤64 | | len | n | fit ≤64 |
---:|---:|---:|---|---:|---:|---:|
| 1–7 | 2,305 | 100.0 % | | 20 | 737 | 58.1 % |
| 8 | 964 | 99.8 % | | 24 | 464 | 40.1 % |
| 10 | 1,278 | 97.8 % | | 28 | 302 | 21.9 % |
| 12 | 1,368 | 93.9 % | | 32 | 176 | 8.0 % |
| 14 | 1,376 | 89.1 % | | 36 | 112 | 0.9 % |
| 16 | 1,173 | 82.1 % | | 40 | 53 | 0.0 % |
| 18 | 888 | 71.4 % | | 42 | 52 | 1.9 % |

The practical consequence: **the encoder cannot decide from the length** — it
must encode and test.  A "short names always fit" rule holds only up to 7
characters; past that an unpredictable 8-character name can fail while a
predictable 42-character one succeeds.

## 3. A generative view

50,000 identifiers drawn from the model (a cycle from the stop token back to
it), `k = 52`:

| | generated | corpus |
|---|---:|---:|
| mean length | 17.03 | 16.97 |
| valid `[A-Za-z_][A-Za-z0-9_]*` | 98.9 % | 100 % |
| exactly a real identifier | 1.64 % | — |
| mean bits | 56.81 | 56.37 |
| fit ≤64 | 68.2 % | 71.3 % |
| fit ≤128 | 92.0 % | 97.1 % |

Examples: `setArgs`, `count`, `signed`, `Crip_Vtblpace`, `enu`,
`loallocingHeliseTyperoindest`, `reclassGroupResponse`, `constromMethod`.

A random member of the 64-bit set therefore *looks* like an identifier — 98.9 %
parse, and the length distribution matches the corpus to a hundredth of a
character — but only **1.6 %** is a real identifier, and its own 128-bit
coverage (92 %) is worse than the corpus's (97 %): the model's generative tail
is **heavier** than the empirical one.  So the residual mass of the bijection
lands on plausible-looking but unreal names, and the *tail* of the set is
worse-behaved than the average real identifier.  This is what the
64-bit set's "usefulness" costs: the code is a good model of the common mass and
a poor one of its own tail.

## What it shows

* At 17–25 kB the 64-bit set covers ~71–73 % of distinct identifiers; the
  128-bit set ~97 %.  Whether that is "useful" depends on the occurrence
  weighting (retired finding: ~92 % of occurrences) and on the vocabulary size
  — `V = 4,478` and `11,758` should recover several points
  ([`MODEL_BUDGET.md`](MODEL_BUDGET.md): 77.0 % and 82.9 % on the smaller
  stride-40 sample).
* There is no length rule for membership: failures are unpredictable
  identifiers of ordinary length, not long ones.
* Sampling is a cheap sanity check on the decoder: the model reproduces the
  identifier *shape* almost exactly, but its tail is heavier than reality.

## Pending

The same run for `V = 4,478` (`k = 105`) and `V = 11,758` (`k = 52`), on a
machine with more than the ~900 MB this box has:

```
python3 scripts/budget64_study.py --dir work/tw4414  --ks 105 --stride 10
python3 scripts/budget64_study.py --dir work/tw11694 --ks 52  --stride 10
```

## Reproducing

```
python3 scripts/budget64_study.py --dir work/tw2040 --ks 52,105 --stride 10
```

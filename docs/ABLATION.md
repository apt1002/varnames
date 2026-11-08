# Ablation study: what each piece is worth

Status: **measured.** One harness
([`scripts/ablation.py`](../scripts/ablation.py)), one held-out set, one
reporting convention. Each arm changes one thing about the shipped model and is
scored the same way: pack the model, decode every held-out identifier through
the packed file (round-trip asserted), and report **bytes**, **mean bits** and
the **fit rate**. The design arguments behind each piece are in the notes cited
in the last section; this file only prices them.

The model-side arms hold `V = 8,192` and the dictionary fixed and use the
shipped operating point `k = 32`, `q = 1`, `κ = 300`, seed 1. Two arms cannot:
case normalisation needs a dictionary built from the raw corpus, and clustering
off is *defined* by a different vocabulary. Measurements are on the standard's
held-out file, `merged_validation.txt`, stride 10, **n = 42,268**.

## 1. The model side

| arm | what changes | bytes | Δ bytes | mean bits | Δ bits | fit ≤64 | Δ fit (pt) |
|---|---|---:|---:|---:|---:|---:|---:|
| base | the shipped configuration | 30,745 | — | 45.218 | — | 85.0 % | — |
| `k = 16` | left clusters 32 → 16 | 29,329 | −1,416 | 45.666 | +0.448 | 84.6 % | −0.4 |
| `k = 64` | left clusters 32 → 64 | 33,321 | +2,576 | 44.952 | −0.266 | 85.3 % | +0.3 |
| `κ = 30` | prior strength 300 → 30 | 30,745 | 0 | 45.322 | +0.104 | 84.7 % | −0.3 |
| `κ = 3,000` | prior strength 300 → 3,000 | 30,745 | 0 | 45.556 | +0.339 | 84.7 % | −0.3 |
| `q = 2` | right clusters per left 1 → 2 | 32,281 | +1,536 | 45.100 | −0.118 | 85.1 % | +0.1 |
| stop weighted | the stop's true mass in the top trees, terminator coded | 30,745 | 0 | 48.468 | +3.250 | 82.1 % | −2.8 |
| 5-bit depths | no depth bias; a depth needs five bits | ~31,901 | +1,156 | 45.217 | −0.001 | 85.0 % | 0.0 |

The `5-bit depths` byte count is an estimate: the same model with one more bit
per depth (a new file version, `MODEL_FORMAT.md` §3.1); every other row is a
packed file the decoder read.

## 2. The data side: case normalisation

This arm needs a second dictionary, built from the **raw** corpus
(`corpus/identifiers.multilang.txt`) instead of the normalised one, with the
same `V`, `k`, `q`, `κ`, seed and sample, and with the same identifiers held
out: a raw line is held out iff its *normalised* form is in the standard's
held-out set. The two models are therefore blind to the same names, and the
only difference is the case convention.

They are scored on the identifiers normalisation leaves unchanged —
**n = 201,290** CamelCase names, the only strings the two models can code
identically:

| dictionary | bytes | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|
| raw corpus | 30,701 | 50.222 | 79.5 % | 98.3 % |
| normalised corpus | 30,745 | 46.261 | 84.3 % | 98.5 % |

Case normalisation is worth **3.96 bits and 4.8 points** on the identifiers it
does not even change, and it costs 44 bytes more: the normalised dictionary
holds fewer distinct strings and spends slightly more rules describing them, and
that is the whole price ([`CASE_NORMALISATION.md`](CASE_NORMALISATION.md)).

## 3. Clustering off, at the same size

The code names a word in two steps: the top stage names a group, the bottom
stage names the word inside it. Drop the grouping and `k = V`: every right
cluster is a word, the top stage is one tree over the whole vocabulary, and
the bottom stage has nothing left to say. That is a first-order Markov code
over words with no table compression, and it is what the four-kilobyte tables
are up against.

The top stage costs `V·(V + 1)/2` bytes at four bits a depth, so matching the
shipped file's size pins the vocabulary at about 240 symbols — 176 pair-merge
words. The flat model comes out slightly **smaller** than the one that ships:

| model | `V` | `k` | bytes | mean bits | fit ≤64 | fit ≤128 |
|---|---:|---:|---:|---:|---:|---:|
| shipped | 8,192 | 32 | 30,745 | 45.218 | 85.0 % | 99.0 % |
| flat | 240 | 240 | 29,710 | 61.386 | 65.6 % | 95.7 % |

At a matched byte budget the factorisation is worth **16.2 bits and 19.4 fit
points**, and even the 128-bit set moves by 3.3. The comparison is not
clustering alone: the flat model's bytes are all table, so its vocabulary
collapses to 239 symbols, while the shipped model spends 4 kB on depths and the
rest on 8,191. That is the trade the frontier
([`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6) is about — table resolution against
vocabulary — and at this size the vocabulary wins by a mile.

The other direction is worse still: a flat model at the shipped vocabulary
would need `8,192 · 8,193 / 2` = **33.6 MB** for its top stage alone, three
orders of magnitude over the whole budget.

## 4. What the table says

**Read bytes against bits, not bits alone.** The frontier
([`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6) sells a 64-bit point for 3–5 kB. Every
row below can be placed on that scale:

* `k = 16` saves 1,416 B for 0.448 bits — **3.2 kB a bit**, on the frontier.
  `k = 64` spends 2,576 B for 0.266 bits — **9.7 kB a bit**, twice the price,
  which is why 32 ships even though 64 has the better code.
* `q = 2` spends 1,536 B for 0.118 bits — **13 kB a bit**, and it is why
  [`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md) refutes quarters.
* `κ` is an interior optimum at the same byte count: 30 and 3,000 both lose
  **about a third of a bit**, and a third of a point, with nothing bought in
  bytes. The prior was chosen by held-out likelihood; the packed harness agrees.
* **5-bit depths** are a byte trade only: one bit per depth instead of the
  bias's four costs 1,156 B — 3.6 % of the file — for 0.001 bits. There is no
  reason to take it, which is why the format searches for a bias that keeps
  the field at four.
* The **stop** is the largest model-side piece in the table: giving the stop its
  true mass and coding the terminator costs **3.25 bits and 2.8 points at zero
  bytes**. That single decision bundles three effects that only exist together
  — the zero weight shortens every other code, the terminator is never written,
  and the canonical integer drops its trailing zeros
  ([`ENCODING.md`](ENCODING.md) §2).
* **The factorisation is the table.** At a matched byte budget, clustering off
  (§3) costs 16.2 bits and 19.4 points — 3.3 on the 128-bit set. The two-stage
  code is not a refinement of the flat one; it is the reason the model fits in
  30 kB at all.
* On the data side, **case normalisation** is worth more than any model-side
  knob here: 3.96 bits and 4.8 points, for 44 bytes. The model side is a set of
  small trades; the corpus is not.

Across the model-side arms the 128-bit set moves by at most 0.3 points: at this
operating point the second budget is not a constraint, so it does not
discriminate between designs. The flat arm is the exception — 95.7 % against
99.0 % — because at 61 bits an identifier starts to need the larger integer.

## 5. What is not in the table, and why

| question | where it is answered |
|---|---|
| how many words (`V`) | the frontier, [`MODEL_BUDGET.md`](MODEL_BUDGET.md) §6: 4,096 / 6,144 / 8,192 |
| the flat Huffman code at a fixed `k` | [`BUDGET64_STUDY.md`](BUDGET64_STUDY.md): 1.9 points for 94 kB |
| separate assignments for the two sides | [`SHARED_CLUSTERS.md`](SHARED_CLUSTERS.md): 16 kB a bit |
| the tokeniser's algorithm | [`TOKENISATION.md`](TOKENISATION.md): a speed question, no rate |
| the build (sample, split, `κ` search) | [`BUILDING.md`](BUILDING.md) |

The model-side arms hold `V` and the dictionary fixed; only the two data-side
arms, and the flat arm whose vocabulary is forced by its byte budget, build
their own. A sweep of `V` at a fixed `k` belongs to the frontier, which already
prices it. The separate-map model is not packable as the format stands, so its
cost is the earlier note's count.

## 6. Caveats

* The `k = 16` row differs by 0.011 bits from the `8,191/16` row of
  [`BUDGET64_STUDY.md`](BUDGET64_STUDY.md) at the same 29,329 bytes. The earlier
  row came from a separately built `k = 16` model; this harness reproduces the
  shipped file exactly, so its own arms are comparable with each other, which is
  what a table of deltas needs.
* The case-normalisation pair is compared *with itself*, not with the shipped
  row: it is scored on 201,290 identifiers, and the two models there differ only
  in the corpus they were built from.
* The flat arm is matched in **bytes, not in one knob**: `k = V` changes the
  table and the vocabulary together, because at this size the table spends the
  whole budget. Its row says what a flat code buys for 30 kB, which is what the
  frontier asks; it is not a controlled diff of `k` alone.
* The `stop weighted` model is a different encoder convention: the terminator is
  written, so the code is longer by construction. It is the decision — zero
  weight, free terminator, trailing zeros — that is being priced, not a
  shippable variant of the same encoder.

## 7. Reproducing

```console
$ python3 scripts/ablation.py --dir work/tw8192ns
work/tw8192ns: 42,268 held-out identifiers
  base              30,745 B  45.218 bits  85.0 %
  …
$ python3 scripts/ablation.py --dir work/tw8192ns \
      --raw-corpus corpus/identifiers.multilang.txt --raw-out build/ablation_raw
$ python3 scripts/ablation.py --dir work/tw8192ns --flat 240
```

The first run takes about seven minutes (one model build per arm); the second
adds the raw dictionary and takes about four minutes more; the flat arm builds
a dictionary of its own, about two minutes. `--json PATH` writes
the table as JSON. Each arm builds from the same code path the standard did, so
a run on another dictionary measures that dictionary's model.

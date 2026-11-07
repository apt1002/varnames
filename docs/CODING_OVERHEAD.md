# Words per identifier, and the cost of a Huffman code

Status: **results at the grid.**  An arithmetic code spends a *fractional*
number of bits per token (`−log₂ P(b|a)`); a Huffman code must spend a whole
number, and the price of that rounding is paid once per token.  The number of
words per identifier is therefore the multiplier on the Huffman penalty — and
the product is small: 0.13–0.19 bits per identifier, 0.25–0.41 % of the total.
The interesting result is the other direction: under the adopted convention,
where the stop token is coded as zero padding, Huffman comes out about a bit per
identifier *ahead* of arithmetic and lifts the 64-bit fit rate by ~1.5 points.

## Setup

`scripts/words_per_identifier.py`, run on the three grid dictionaries
(`work/tw4096ns`, `tw6144ns`, `tw8192ns`), `kappa = 300`, held-out validation at
stride 10 (`n = 42,268` identifiers).  Because the `assoc` transition depends on
the left *cluster* only, a per-cluster Huffman tree is exactly realisable, and
its code lengths are derivable from the stored `(c, D)` at load time — so the
codebook costs no storage.

## Words per identifier

| `V` | mean | median | p90 | p99 | max | tokens (stop included) | ≤3 words | ≤5 words | ≤8 words |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4,096 | **4.71** | 4 | 8 | 14 | 71 | 5.71 | 37.7 % | 73.9 % | 93.1 % |
| 6,144 | **4.30** | 4 | 7 | 13 | 71 | 5.30 | 45.3 % | 79.5 % | 95.3 % |
| 8,192 | **4.06** | 4 | 6 | 12 | 71 | 5.06 | 49.9 % | 83.0 % | 96.4 % |

A bigger word list buys length as well as fidelity: from `V = 4,096` to 8,192
the mean falls by 0.65 words and the p90 by two words, so the same Huffman
penalty is multiplied by 0.89 of the tokens.  (For the record, the
pre-expansion `V = 2,104` list needed 5.74 words per identifier, so the first
doubling is the expensive one: 5.74 → 4.71.)

## Huffman vs arithmetic

Penalties in bits per identifier; `fit` columns are for 64 and 128 bits.

| `V` | `k` | arithmetic | Huffman | penalty | per token | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4,096 | 16 | 51.462 | 51.624 | **+0.162** (0.31 %) | 0.028 | 77.8 % → **78.0 %** | 98.1 % → 98.1 % |
| 4,096 | 32 | 51.245 | 51.412 | **+0.167** (0.33 %) | 0.029 | 78.1 % → **78.4 %** | 98.1 % → 98.2 % |
| 4,096 | 64 | 50.528 | 50.712 | **+0.184** (0.36 %) | 0.032 | 78.9 % → **79.2 %** | 98.3 % → 98.3 % |
| 6,144 | 16 | 49.317 | 49.443 | **+0.126** (0.25 %) | 0.024 | 80.5 % → **80.7 %** | 98.5 % → 98.5 % |
| 6,144 | 32 | 48.959 | 49.085 | **+0.126** (0.26 %) | 0.024 | 80.9 % → **81.2 %** | 98.5 % → 98.5 % |
| 6,144 | 64 | 48.626 | 48.814 | **+0.188** (0.39 %) | 0.035 | 81.3 % → **81.5 %** | 98.6 % → 98.6 % |
| 8,192 | 16 | 47.727 | 47.873 | **+0.147** (0.31 %) | 0.029 | 82.5 % → **82.8 %** | 98.8 % → 98.8 % |
| 8,192 | 32 | 47.485 | 47.679 | **+0.194** (0.41 %) | 0.038 | 82.8 % → **83.0 %** | 98.8 % → 98.8 % |
| 8,192 | 64 | 47.284 | 47.477 | **+0.194** (0.41 %) | 0.038 | 83.1 % → **83.3 %** | 98.8 % → 98.8 % |

The per-identifier penalty at `V = 4,096, k = 64` is min −19.0, median +0.19,
p90 +1.11, max +8.7 bits — and Huffman comes out **shorter on 39–44 % of
identifiers**, which is why the 64-bit fit rate *rises* rather than falls at all
nine points.

Two things to notice.  The penalty **does not grow with the token count**: at
`k = 16` it is 0.126–0.162 bits across `V`, although the tokens per identifier
fall from 5.71 to 5.06.  What does grow is the per-token rounding (0.032 →
0.038 bits at `k = 64`), because a larger `V` means more leaves per tree and a
longer tail of medium-probability words that must take integer lengths above
their ideal.

## Two trees instead of one (the factored code)

The `assoc` transition factors *exactly* into a cluster step and a word step:

```
P(b | a) = P(j | i) · P(b | j),    i = lcl(a),  j = rcl(b),
P(j | i) = Cc[j]·D[i,j] / den[i],  P(b | j) = c[b] / Cc[j]
```

so a small model can code each token in two stages and pay the whole-bit
rounding **twice**: one Huffman tree per left cluster over the `k` clusters, plus
one tree per right cluster over its own member words.  Measured on the same
held-out set:

| `V` | `k` | factored penalty | % | cluster step | word step | fit ≤64 |
|---:|---:|---:|---:|---:|---:|---:|
| 4,096 | 16 | **+1.211** | 2.35 % | 0.028 | 0.184 | 77.8 % → **77.1 %** |
| 4,096 | 32 | **+0.868** | 1.69 % | 0.041 | 0.111 | 78.1 % → **77.7 %** |
| 4,096 | 64 | **+1.394** | 2.76 % | 0.043 | 0.201 | 78.9 % → **78.2 %** |
| 6,144 | 16 | **+1.299** | 2.63 % | 0.041 | 0.204 | 80.5 % → **79.6 %** |
| 6,144 | 32 | **+1.249** | 2.55 % | 0.033 | 0.202 | 80.9 % → **80.2 %** |
| 6,144 | 64 | **+1.307** | 2.69 % | 0.041 | 0.205 | 81.3 % → **80.4 %** |
| 8,192 | 16 | **+1.260** | 2.64 % | 0.038 | 0.211 | 82.5 % → **81.9 %** |
| 8,192 | 32 | **+1.289** | 2.71 % | 0.037 | 0.218 | 82.8 % → **82.0 %** |
| 8,192 | 64 | **+1.322** | 2.79 % | 0.041 | 0.220 | 83.1 % → **82.3 %** |

The per-token split adds up exactly (0.041 + 0.111 = 0.152 bits/token at
`V = 4,096, k = 32`).

So yes — **two penalties, and they are additive**, but the factored code costs
**5–10×** the flat one (0.87–1.39 vs 0.13–0.19 bits/identifier).  This is
expected, not a defect: the flat code is the Huffman code of the *joint*
`P(b|a)`, which is optimal among prefix codes; a product of two prefix codes is
a valid but generally *sub*optimal code for the same source, so it can only
lose.  Each stage is individually near its own entropy (0.03–0.04 and
0.11–0.22 bits/token), and their sum is still ~0.15–0.26 bits/token against
~0.03–0.04 for the joint.  The word step dominates throughout: leaf set `V`
against `k`, long-tailed, so many medium-probability words have to take integer
lengths above their ideal bits.

Neither codebook costs model bytes: both are derivable at load time from the
stored `(c, D, lcl, rcl)`.  The only difference is startup work — `k` trees of
`V` leaves, versus `k` trees of `k` leaves plus `k` trees totalling `V` leaves.

Consequence for the 64-bit set: the factored code *lowers* the fit rate by
0.4–0.9 points, whereas the flat code raised it by 0.2–0.3.  If a Huffman coder
is wanted, use **one tree per left cluster over the joint**, not two trees.

## The zero-weight stop changes the verdict

Every number above charges the stop token like any other symbol.  That is the
right convention for an *arithmetic* code, which cannot end an identifier for
free ([`ENCODING.md`](ENCODING.md) §2).  It is the wrong one for the Huffman
code: the all-zeros codeword is never written, so the padded zeros *are* the
terminator and the stop's bits are never spent.  Building each tree with the
stop's weight driven to zero gives the other symbols the lengths of the
renormalised distribution, and that changes what the code costs.

`words_per_identifier.py --zero-stop`, stride 10 (`n = 42,268`), `kappa = 300`:

| `V`, `k` | arithmetic (cyclic) | arithmetic (codec) | Huffman (stop weight 0) | Huffman − codec | fit ≤64 (codec → Huffman) |
|---|---:|---:|---:|---:|---:|
| 4,096, 32 | 51.245 | 49.368 | **48.339** | **−1.029** | 79.7 % → **81.3 %** |
| 8,192, 16 | 47.727 | 46.031 | **45.027** | **−1.004** | 83.8 % → **85.3 %** |

* The renormalisation is worth **1.760 / 1.785 bits/identifier** (0.308 / 0.353
  bits/token), so the ideal cost of the words is `49.368 − 1.760 = 47.61` and
  `46.031 − 1.785 = 44.25`; the Huffman rounding on top is 0.73 / 0.78
  bits/identifier (0.13 / 0.15 bits/token).
* So the flat code **beats the arithmetic reference outright** once the stop is
  free — by 1.03 / 1.00 bits/identifier, with `fit ≤ 64` rising by 1.6 / 1.5
  points.  The terminator is worth more than the rounding costs.
* The all-zeros codeword lands at depth 28 (longest word code 27 bits), so the
  decoder may have to read up to 28 zeros of padding to see the terminator —
  free, but the standard has to say so.

One more bit comes for free and is not in the table: the code occupies the low
bits of the integer, so whatever zeros sit at the top of the final codeword are
indistinguishable from the terminator's padding.  On average that is one bit per
identifier (`ENCODING.md` §2), so the Huffman advantage over arithmetic is about
**2 bits/identifier**, and `fit ≤ 64` is ~1 point better than a sum of codeword
lengths suggests.

## What it shows

* **Huffman is nearly free here** — 0.13–0.19 bits per identifier, 0.25–0.41 %
  of the total — even though the multiplier is 5–5.7 coded tokens per
  identifier.  The reason is that the cluster-conditional distributions are
  extremely skewed, and Huffman's redundancy is small for skewed distributions:
  0.024–0.038 bits per token, not the ~0.5 bits a uniform-ish alphabet would
  suggest.
* **The histogram alone would have misled.** 5.71 tokens × a worst-case
  ~1 bit/token would be ~5.7 bits/identifier (11 %); the measured penalty is
  30–40× smaller.
* **Huffman can beat the ideal per symbol.**  A symbol with `P = 0.4` gets a
  1-bit codeword where the ideal is 1.32 bits, so individual identifiers can come
  out *shorter* than arithmetic — 39–44 % of them do — and the 64-bit coverage
  goes slightly *up*.  This is the ordinary behaviour of Huffman lengths inside
  the entropy bound, and it means a 64-bit set built on Huffman would be
  marginally *larger*, not smaller.
* **Under the adopted convention the sign flips.**  Freeing the stop's
  transition costs the code nothing (the zeros do the work) and returns about
  1.8 bits, of which the rounding takes back 0.73–0.78; the net is a full bit in
  Huffman's favour and ~1.5 points of fit.  That is why the shipped code is
  Huffman with a zero-weight stop, not arithmetic, and why `ENCODING.md` §2
  spends so long on the terminator.
* **Factor first, code second — or don't factor at all.**  Coding the model's
  two stored factors in two Huffman steps multiplies the rounding by ~7.  The
  rounding is the price of the *code*, not of the model, so the cheap answer is a
  single tree per left cluster over the joint transition, which the stored
  `(c, D)` already define.
* Practical read: the choice between Huffman and arithmetic is **not** a size
  argument.  Arithmetic remains simpler to frame (a cyclic code with the stop as
  zeros beyond the target length); Huffman needs a tree per left cluster and, as
  the next section shows, is worth about a bit — which is what the standard
  takes.

## Reproducing

```sh
for d in work/tw4096ns work/tw6144ns work/tw8192ns; do
  python3 scripts/words_per_identifier.py --dir $d --ks 16,32,64 --stride 10
done
# the zero-weight stop (the adopted convention), one cell at a time:
python3 scripts/words_per_identifier.py --dir work/tw4096ns --ks 32 --stride 10 --zero-stop
python3 scripts/words_per_identifier.py --dir work/tw8192ns --ks 16 --stride 10 --zero-stop
```

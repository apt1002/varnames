# Words per identifier, and the cost of a Huffman code

Status: **results.**  An arithmetic code spends a *fractional* number of bits per
token (`−log₂ P(b|a)`); a Huffman code must spend a whole number, and the price
of that rounding is paid once per token.  The number of words per identifier is
therefore the multiplier on the Huffman penalty — but the per-token redundancy
turns out to be tiny, so the product is small.

## Setup

`scripts/words_per_identifier.py`.  `V = 2,104` (`work/tw2040`), `kappa = 300`,
held-out validation at stride 10 (`n = 22,954` identifiers, 154,617 tokens).
Because the `assoc` transition depends on the left *cluster* only, a per-cluster
Huffman tree is exactly realisable, and its code lengths are derivable from the
stored `(c, D)` at load time — so the codebook costs no storage.

## Words per identifier

| words | identifiers | cumulative | | words | identifiers | cumulative |
---:|---:|---:|---|---:|---:|---:|
| 1 | 16 | 0.1 % | | 8 | 1,428 | 85.8 % |
| 2 | 1,402 | 6.2 % | | 9 | 956 | 90.0 % |
| 3 | 3,957 | 23.4 % | | 10 | 654 | 92.8 % |
| 4 | 4,339 | 42.3 % | | 12 | 332 | 96.2 % |
| 5 | 3,765 | 58.7 % | | 15 | 122 | 98.4 % |
| 6 | 2,800 | 70.9 % | | 18 | 55 | 99.2 % |
| 7 | 1,987 | 79.6 % | | 20+ | ~140 | 100 % |

**mean 5.74 words per identifier** (median 5, p90 10, p99 18, max 51); counting
the stop token, the coder spends **6.74 tokens per identifier**.

## Huffman vs arithmetic

| `k` | arithmetic | Huffman | penalty | per token | fit ≤64 | fit ≤128 |
|---:|---:|---:|---:|---:|---:|---:|
| 52 | 56.368 bits/id | 56.558 | **+0.190** (0.34 %) | 0.028 bits | 71.3 % → **71.6 %** | 97.1 % → 97.1 % |
| 105 | 55.135 bits/id | 55.361 | **+0.225** (0.41 %) | 0.033 bits | 72.6 % → **72.9 %** | 97.4 % → 97.4 % |

The per-identifier penalty is min −3.60, median +0.17, p90 +1.09, max +5.56 bits
(`k = 52`) — and Huffman comes out **shorter on 40 % of identifiers**, which is
why the 64-bit fit rate *rises* rather than falls.

## Two trees instead of one (the factored code)

The `assoc` transition factors *exactly* into a cluster step and a word step:

```
P(b | a) = P(j | i) · P(b | j),    i = lcl(a),  j = rcl(b),
P(j | i) = Cc[j]·D[i,j] / den[i],  P(b | j) = c[b] / Cc[j]
```

so a small model can code each token in two stages and pay the whole-bit rounding
**twice**: one Huffman tree per left cluster over the `k` clusters, plus one tree
per right cluster over its own member words.  Measured on the same held-out set:

| `k` | arithmetic | flat (1 tree per left cluster) | factored (2 trees) | cluster step | word step | fit ≤64 |
|---:|---:|---:|---:|---:|---:|---:|
| 52 | 56.368 | +0.190 (0.34 %) | **+1.402** (2.49 %) | 0.036 | 0.173 | 71.3 % → **70.2 %** |
| 105 | 55.135 | +0.225 (0.41 %) | **+1.590** (2.88 %) | 0.041 | 0.195 | 72.6 % → **71.4 %** |

Penalties in bits per identifier; the per-token split is in bits/token and adds
up exactly (0.036 + 0.173 = 0.209 ≈ 0.208 total at `k = 52`).

So yes — **two penalties, and they are additive**, but the factored code costs
**~7×** the flat one (1.4–1.6 vs 0.19–0.23 bits/identifier).  This is expected,
not a defect: the flat code is the Huffman code of the *joint* `P(b|a)`, which is
optimal among prefix codes; a product of two prefix codes is a valid but
generally *sub*optimal code for the same source, so it can only lose.  Each stage
is individually near its own entropy (0.036 and 0.173 bits/token), and their sum
is still ~0.24 bits/token against ~0.03 for the joint.  Both steps pay one
rounding per token, but the word step dominates (0.173 vs 0.036).  The two steps
differ in shape: the cluster step averages 3.94 bits of entropy over ~44 reachable
clusters (top cluster carries 0.25 of the row mass), while the word step averages
~4.4 bits over the member words of a cluster — long-tailed, with a much larger
leaf set (`V` leaves in total), so many medium-probability words have to take
integer lengths above their ideal bits.

Neither codebook costs model bytes: both are derivable at load time from the
stored `(c, D, lcl, rcl)`.  The only difference is startup work — `k` trees of
`V` leaves, versus `k` trees of `k` leaves plus `k` trees totalling `V` leaves.

Consequence for the 64-bit set: the factored code *lowers* the fit rate by
~1.1 points, whereas the flat code raised it slightly.  If a Huffman coder is
wanted, use **one tree per left cluster over the joint**, not two trees.

## The zero-weight stop changes the verdict

Every number above charges the stop token like any other symbol.  That is the
right convention for an *arithmetic* code, which cannot end an identifier for
free (`ENCODING.md` §2).  It is the wrong one for the Huffman code: the
all-zeros codeword is never written, so the padded zeros *are* the terminator
and the stop's bits are never spent.  Building each tree with the stop's weight
driven to zero gives the other symbols the lengths of the renormalised
distribution, and that changes what the code costs.

`work/tw2040ns`, `V = 2104`, `k = 52`, `kappa = 300`, stride 10 (22,954 ids,
154,615 tokens); `words_per_identifier.py --zero-stop`:

| convention | arithmetic | Huffman (stop weight 0) | Huffman − arithmetic |
|---|---:|---:|---:|
| cyclic (both stop edges charged) | 56.463 | 53.389 | −3.074 |
| codec (the stop's transition is free) | 54.426 | **53.389** | **−1.037** |

* The renormalisation is worth **1.736 bits/identifier** (0.258 bits/token), so
  the ideal cost of the words is `54.426 − 1.736 = 52.690`; the Huffman rounding
  on top is 0.699 bits/identifier (0.104 bits/token).
* So the flat code **beats the arithmetic reference outright** once the stop is
  free — by 1.04 bits/identifier at `k = 52`, with `fit <= 64` rising from
  73.0 % to 74.8 %.  The terminator is worth more than the rounding costs.
* The all-zeros codeword lands at depth 26 (longest word code 25 bits), so the
  decoder may have to read up to 26 zeros of padding to see the terminator —
  free, but the standard has to say so.

Measured on the pre-rebuild corpus; re-measured with the rest under the rebuild.

## What it shows

* **Huffman is nearly free here** — ~0.2 bits per identifier, 0.35 % of the total
  — even though the multiplier is large (6.74 coded tokens per identifier).  The
  reason is that the cluster-conditional distributions are extremely skewed, and
  Huffman's redundancy is small for skewed distributions: 0.028 bits per token,
  not the ~0.5 bits a uniform-ish alphabet would suggest.
* **The histogram alone would have misled.** 6.74 tokens × the worst-case
  ~1 bit/token would be ~7 bits/identifier (12 %); the measured penalty is 40×
  smaller.
* **Huffman can beat the ideal per symbol.**  A symbol with `P = 0.4` gets a
  1-bit codeword where the ideal is 1.32 bits, so individual identifiers can come
  out *shorter* than arithmetic — 40 % of them do — and the 64-bit coverage goes
  slightly *up*.  This is the ordinary behaviour of Huffman lengths inside the
  entropy bound, and it means a 64-bit set built on Huffman would be marginally
  *larger*, not smaller.
* **Factor first, code second — or don't factor at all.**  Coding the model's
  two stored factors in two Huffman steps multiplies the rounding by ~7.  The
  rounding is the price of the *code*, not of the model, so the cheap answer is a
  single tree per left cluster over the joint transition, which the stored
  `(c, D)` already define.
* Practical read: the choice between Huffman and arithmetic is **not** a size
  argument.  Arithmetic remains preferable for its simplicity of framing (the
  stop token as zeros beyond the target length, per
  [`PRODUCTISATION.md`](PRODUCTISATION.md)); Huffman would need a tree per left
  cluster and would gain nothing worth the complexity.

## Reproducing

```
python3 scripts/words_per_identifier.py --dir work/tw2040 --ks 52,105 --stride 10
```

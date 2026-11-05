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
* Practical read: the choice between Huffman and arithmetic is **not** a size
  argument.  Arithmetic remains preferable for its simplicity of framing (the
  stop token as zeros beyond the target length, per
  [`PRODUCTISATION.md`](PRODUCTISATION.md)); Huffman would need a tree per left
  cluster and would gain nothing worth the complexity.

## Reproducing

```
python3 scripts/words_per_identifier.py --dir work/tw2040 --ks 52,105 --stride 10
```

# Codesigning the assignment and the code (a sketch)

The idea changes which clusters exist, not how they are coded: the decoder
cannot tell a codesigned model from any other with the same `V` and `k`
(`ENCODING.md` §§2–4).

**Status: a design sketch, not implemented.**  `scripts/codesign.py` does not
exist.  What has changed since it was written: the code side is now measured as
nearly exhausted (the flat Huffman penalty is 0.13–0.19 bits/identifier and the
zero-weight stop more than pays it back — `ENCODING.md` §2–3,
`CODING_OVERHEAD.md`), while the
model is not (7.8–9.1 bits above the full table, `BUDGET64_STUDY.md`).
So the thing worth codesigning is the **model term** — which cells share a
block entry and a membership — not the codeword assignment.  The budget for any
such idea is the factorisation penalty itself, now measured at
**0.87–1.39 bits/identifier** across the grid (`CODING_OVERHEAD.md`), not the
1.2 it was when this was drafted.  The plan item is in `PLAN.md`.

The quarters are a fixed lattice imposed before the code is built; a better
design changes the clustering *and* the trees together.  The objective is

    minimise  Σ_b N(b) · len(code(b) | cluster(b))  +  λ · (model bytes)

over (assignment, per-cluster trees).  Given the trees, the assignment is a
facility-location problem; given the assignment, the trees are Huffman.  That is
coordinate descent, and it is cheap because the marginal cost of moving one word
between two clusters is computable exactly: the change in the two trees' Huffman
costs (from the two probability multisets) plus the (constant) membership bits.

Two structural notes for whoever implements it:

* Huffman is not a smooth function of the cell contents.  The assignment that
  minimises KL (what `k`-means does) is *not* the assignment that minimises code
  length: Huffman punishes a single large leaf in a cell (`p_max` is the
  redundancy bound), so a code-aware clustering will push the long tail into
  cells of its own and keep the heads together.  Expect the optimum to look
  "less Hellinger, more log-bucketed".
* Because the model bytes move in whole clusters (one more cluster costs
  `V·log₂((k+1)/k) ≈ V/k` bits of membership, about `2k` bits of block and `k`
  code lengths), the search is over a small integer grid (`k`, `q`); it is a
  frontier walk, not a gradient.

Walking before running: measure the *gap* between the current assignment's code
and the best code for that same assignment (that is the CF penalty, already
known), then the gap between that and the best code over all assignments of the
same number of cells (a local search from the `k`-means optimum).  The second
gap bounds what codesign can buy.

## A single-phase build: what actually gets modified

The question is whether the separation (cluster, then pair inside the cluster)
can be collapsed into one phase that chooses pairs partly on Hellinger distance.
It can, but it has to be at the level of **cells**, not codewords — and the two
levels need separating, because only one of them pays.

**Inside a tree the merge key is already optimal, and the geometry is absent.**
A per-cell tree's leaves are words and their weights are `p(b | cell) ∝ p(b)`,
the word's global frequency renormalised to the cell.  Huffman's "merge the two
least probable subtrees" is a theorem about that objective, so any other pairing
— including one that prefers contextually similar words as siblings — costs bits
and buys nothing: the block model `D` is where similarity is spent, and the tree
never sees context.  Two Hellinger-close words can have wildly different
frequencies, which is exactly the case Huffman wants to separate.

**One level up, the two greedy algorithms are the same shape.**  Both are
repeated "merge the cheapest pair" loops:

* Huffman's key is the merged mass; summed over merges it *is* the expected code
  length.  This is Huffman with `k = 1`.
* Hellinger/Ward `k`-means' key is the increase in within-cell distortion,
  which for centroids is `w_A w_B / (w_A + w_B) · ‖θ_A − θ_B‖²`, and
  `‖√p − √q‖² = 2H²`.  This is the same loop with the code term switched off
  and `k` fixed.

So the codesign is a single merge loop that starts at `k = V` (each word its own
cell) and merges until it stops, with one compound key:

    Δ(A,B) =  λ_fit · [ w_A w_B / (w_A + w_B) ] · 2H²(θ_A, θ_B)    (block fit worsens)
            + λ_code · [ code length of A∪B  −  A  −  B ]           (one tree, not two)
            − [ model bits freed by one fewer cell ]                (≈ V log₂(k/(k−1)) + 3k)

Two consequences worth noting:

* **`k` stops being a sweep parameter.**  It is where merges stop paying.  Plain
  Hellinger clustering and plain Huffman are the two degenerate settings of λ.
* **The merge key can be evaluated exactly and cheaply.**  The entropy part of
  the code term is additive (`Σ p log p` is kept per cell), the Huffman
  redundancy is bounded by `p_max`, which is also kept per cell, so
  `Δcode ≈ [H(A∪B) + p_max(A∪B)] − [H(A) + p_max(A)] − [H(B) + p_max(B)]`,
  scaled by the token counts of the words involved.  The fit term's exact
  version (`Σ_a w_a D(p(·|a) ‖ pooled)`) is `O(|A|+|B|)` from cached row sums,
  and the Ward form above is its `O(1)` surrogate — use Ward in the heap, exact
  KL for the final acceptance test.  The heap-with-lazy-invalidation machinery
  is the one `tree_words.py` already uses for the most-frequent-pair merge.

The point of the compound key is *not* to let similarity override probability
inside a tree; it is to decide **which words share a tree**, which is the only
place the two objectives genuinely conflict.

**Why the tree build should *not* be modified.**  An earlier draft proposed
constraining the final merges so the `q` survivors come out near-equal in mass.
That is backwards: equal survivors are the case where finishing the build costs
only `log₂ q` bits, so there is no loss for the shared top stage to recover, and
forcing them perturbs the greedy grouping inside every quarter.  The surviving
subtrees must be whatever the greedy build produced — the inequality at the top
*is* the thing being sold.  What a codesign can legitimately change is which
words are in the same **cell** (above), not how the tree inside a
cell is shaped.

**Walking (`scripts/codesign.py`, ~150 lines, reuses `cluster_words.py`):**

1. For an existing `k`-means assignment at `(V, k)`, build the real Huffman
   trees and record `Σ N(b)·len(b)` — the current code's cost.
2. Run the merge loop with `λ_fit = 0` (code + model only) down to the same `k`.
   If it does not beat the `k`-means cells on bits at matched `k`, codesigning
   has nothing to win and only the model side matters — a one-afternoon answer.
3. If it does, sweep `λ_fit` and let `k` fall out; compare the frontier with the
   `k`-means frontier at matched model bytes (the shape used in `SHARED_CLUSTERS.md`).
4. Independently of the loop, run the quarters accounting of
   [`CLUSTER_QUARTERS.md`](CLUSTER_QUARTERS.md) step 3: over
   every cell, sum the masses of the last `q − 1` merges (the in-cell loss that
   truncation avoids) and compare it with the top stage's charge for the same
   tokens (`H(quarter | left cluster)` plus a redundancy bound).  This needs no
   new code — only the merge masses, which the build already knows — and it
   says whether any `q` can pay before anything is built.  Do it first.

## A merge-loop formulation (proposal, under discussion)

An alternative to the coordinate descent above: make the clusters *be* Huffman
trees and alternate the usual two phases — recompute each cluster's centroid
(the **normalised mean of the `√p` vectors**, not `√` of the mean), then rebuild
the partition by merging.  Phase 2 repeatedly takes the globally least probable
remaining tree `t` and merges it into the cluster minimising

    [Hellinger cost of moving t there]  +  [Δ_CS of the merge]

Two results are worth keeping, whichever way the design goes:

* **The merge cost has a closed form.**  With `a`, `b` the two trees' masses,

      Δ_CS = (a + b)·(1 − h₂(a/(a+b))),      h₂ = binary entropy in bits

  and in any base `b`, `Δ_CS = (a+b)(log_b 2 − h_b(a/(a+b)))` — "one unit of
  log 2 minus the binary entropy" — so the identity is base-free; the numbers
  below are in bits because the code lengths and the fit rates are.

  i.e. zero exactly when the masses are equal, maximal when one is zero, and
  *increasing in the partner's mass*.  Consequences: with the Hellinger term
  switched off the rule is exactly Huffman; and at a fixed point, where the
  Hellinger term is the same for every partner inside the chosen cluster, the
  tree built inside each cluster is the Huffman tree for that cluster.  That is
  the necessary condition, and it holds.
* **The fit term can only override close mass ratios.**  As bits per occurrence
  of `t`, `Δ_CS/a = (1 − h₂(θ))/θ`.  The fit term as proposed is `N(t)·(2H)²`
  (the metric that approximates the KL, §"Calibration" below), which saturates
  at 4 — 5.8 bits — when the supports are disjoint.  Break-even mass ratios:
  1.4:1 for a 0.05-bit fit, 2:1 for 0.25 bits, 9.5:1 even for maximally
  dissimilar clusters.  So the fit decides only between partners of similar
  mass and the resulting clusters are **mass-stratified** — they overlap in
  Hellinger space by construction.

  That is not automatically fatal: a *quarter* is a code-only refinement (the
  block `D` stays `k × k`), so quarters may overlap almost perfectly and cost
  nothing, whereas a codesigned cluster *is* the block model's cell, so its
  overlap is charged through `D`.  The budget for the whole idea is therefore
  the factorisation penalty itself — the 1.2 bits/identifier between the flat
  and two-tree codes — and any fit damage larger than that is a net loss.

Calibration, which is where the factor of two lives: `(2H)² ≈ KL` **in nats**.
For `p ≈ q` the second-order expansion gives `KL(nats) ≈ ½Σ(p−q)²/q`,
`2H² = ‖√p − √q‖² ≈ ¼Σ(p−q)²/q` and `(2H)² ≈ ½Σ(p−q)²/q`, so `(2H)²` is the KL
in nats and `2H²` is exactly half of it.  In **bits**, `KL ≈ (2H)²/ln 2 =
1.4427·(2H)²`.  So a fit term written as `(2H)²` and a code term in bits are
not in the same units: multiply the fit by 1.4427, or — better — calibrate it
against measured block-model bits, since the proxy is only exact for nearby
distributions.  (The `2H²` used for the *geometry* — the Ward key and the
`k`-means centroid — is the squared embedding distance, a different quantity,
exactly half of `(2H)²`; the constant does not matter there because it does not
move an argmin.)

Open: no descent proof between passes (phase 2 assigns trees greedily in mass
order, so the previous partition is only reproducible at a fixed point), and a
cluster reduced to one tree has no stay-put option.  A fixed point is
self-consistent; monotonicity is empirical.


# Plan — parallel lines of research

Living index of the open threads. Each line gets a one-line status and a
pointer to the document / script that owns it. `[ ]` = open, `[~]` = in
progress, `[x]` = done.

## Standing background (done, load-bearing)

- [x] Corpus build + case normalisation — `docs/CORPUS.md`,
      `docs/CASE_NORMALISATION.md`.
- [x] Character-level fixed-budget compressibility — `docs/CODE_LENGTHS.md`.
- [x] Prefix/suffix adjacency model, low-rank + reversal symmetry —
      `docs/ADJACENCY_MODEL.md`.
- [x] Square-root (Hellinger) factorisation + unobserved-pairs counting fix
      (`M + κ·N·P_mar`, κ = 1000) — `docs/HELLINGER_FACTORISATION.md`.
- [x] Choosing `k` and `N` for the model size — `docs/CLUSTER_SIZE_STUDY.md`.
- [x] Dictionary (pair-merge) model: CS identity, per-merge delta, `Δ⁽¹⁾ = 0`,
      entropy form, `Δ = O((m−1)²)` — `docs/TREE_WORDS.md`,
      `scripts/check_merge_delta.py`.

## A. Dictionary / pair-merge theory (`docs/TREE_WORDS.md`)

- [~] **A1. Prove `Δ < 0` exactly** (not just to second order). Intuition:
      incrementing `NUM_PAIRS` should always shrink `CS`. Standard of proof:
      symbolic algebra + numerical experiment. *Status: leading-order proof
      (non-positive quadratic form) + exact entropy form + exhaustive numerical
      sign check (`scripts/check_merge_delta.py --exhaustive`). Both `ΔS1` and
      `ΔS2` are shown `≤ 0`, but the exact `ΔS2 ≤ ΔS1` is still open; the only
      counterexamples to the raw inequality are doubled-word merges with a run
      `uuu`, which the standing assumption excludes (see A2). A checkable
      sufficient condition for `Δ = 0` is proved in `docs/TREE_WORDS.md` (the
      trigram identity `m = 1` together with the `(a,b,a,b)` 4-gram identity)
      and exercised by `check_sufficient_condition`; whether the pair secretly
      forces every `m₄ = 1` is left open.*
- [x] **A2. Relax "no threefold repetition".** When `uu` is the most common
      pair, emit `(u^n)` words for every run length `n` present, instead of a
      single `(uu)`. The *run-aware rule* is defined and proved sign-safe in
      `docs/TREE_WORDS.md` §9.1 ("Relaxing `no uuu`"): collapse maximal runs
      `u^k` to flat `(u^k)` words, one per
      length. Verified by `check_run_aware` in `scripts/check_merge_delta.py`
      (`0` positive `Δ` over `41 167` enumerated steps) and a heavier
      cross-check (`118 597` corpora × ≤40 steps, `4 000` random run-heavy
      corpora × ≤60 steps — `0` positives), so `Δ ≤ 0` survives the relaxation.
      Replaces the earlier global-RLE idea.
- [x] **A3. Greedy alternative.** Pick the pair with the largest `Δ` instead of
      the most frequent pair. `docs/DICTIONARY_RULES.md` §A3, driven by
      `scripts/dict_experiments.py`: the `Δ` rule wins by +4–6% on structured
      synthetic data but only +0.2–0.3% on real identifiers (and reverses by
      `NUM_PAIRS = 24`) — the frequency rule is a robust proxy.
- [x] **A4. `(uv)` vs `(u^n)` crossover.** For `uuuuv`, when should the model
      prefer `(u^4)v` over `uuu(uv)`? `docs/DICTIONARY_RULES.md` §A4: a single
      run word `(u^k)` beats the boundary `(uv)` iff `(k−1)·#runs(k) > N(u,v)`
      (correct `10/10` on the test grid); with spread run lengths the boundary
      takes the slot but the full run-aware rule still wins. Reuses A2's
      `scripts/check_merge_delta.py` theory + `scripts/dict_experiments.py`.
- [x] **A5. Rewrite `TREE_WORDS.md` for pedagogy.** One of `m`/`E` only (`m`
      kept throughout, no `e^E`), history removed, textbook order: corpus →
      dictionary → score → one-merge delta → `m` factorisation → entropy form →
      second order → sign/run-aware → cycle identity → remarks. Git history is
      the archive.

## B. Adjacency matrix construction (new doc)

- [x] **B1. New `docs/ADJACENCY_MATRIX.md`** — the canonical "how to build the
      adjacency matrix", including the choice of `κ`. Experiment docs
      (`HELLINGER_FACTORISATION.md`, `ADJACENCY_MODEL.md`) should *refer* to it
      rather than repeat it.

## C. Apply the dictionary model to `merged.txt`

- [x] **C1. Word × word adjacency counts** by tokenising every string with the
      pair-merge dictionary (dictionary-based split, *not* the character-level
      split used so far).  `scripts/tree_words.py train` builds the greedy BPE
      dictionary, tokenises the corpus and saves the cyclic word bigram matrix
      (`work/tw{96,512,2040}/adj.npz`).
- [x] **C2. Fill unobserved adjacencies** with the current best-practice prior.
      The `kappa` prior of `ADJACENCY_MATRIX.md` §6 adapted to the word bigram
      matrix (`tree_words.py score`); the matrix prefers `kappa ≈ 30–100`, not
      the character default 1000 (documented + swept).
- [x] **C3. Held-out compressibility** — sample identifiers, score under the
      model, report the fraction under 64 bits and 128 bits; compare with
      `docs/CODE_LENGTHS.md`.  `docs/WORD_COMPRESSIBILITY.md`.  At equal
      dictionary size the character model wins clearly (vocab ≈ 2100: 55.2 vs
      63.9 mean bits, 72.6% vs 61.7% in 64 bits).
- [ ] **C4. "Breaking open the pair" prior.** For an unobserved `(uv)w`, seed the
      count from the observed `vw` (recursively); when both words are pairs,
      break the later (rarer) one; base case = single characters.
      *Detail + feasibility pass first.*

## Housekeeping / deferred regenerations

- [x] **H1. Rebuild `work/*/pair_stats.txt` and `pair_factors_L*.npy`** with the
      raised `randomized_svd` `n_iter=8` default — done 2026-10-30,
      `work/afk_pairmatrix.sh`, log `work/afk_pairmatrix.log`
      (all 5 `PAIR_THRESHOLDS`, ~15 s each).
- [ ] **H2. Corpus hardening** (deferred, optional): Ruby heredoc markers /
      UUID fixtures.

## Decisions to confirm (see questions to the PI)

- D1. New-doc name + how much of `ADJACENCY_MODEL.md` folds into it.
- D2. Which `NUM_PAIRS` values to prototype (and how to map them to the
      `common<T>` vocabularies).
- D3. Held-out sample size / training-split policy for C3.
- D4. Whether C4's prior is wanted inside C2, or kept as a separate study.

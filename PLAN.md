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
      `u^k` to flat `(u^k)` words, one per length.  Verified by
      `check_run_aware` in `scripts/check_merge_delta.py`
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

- [ ] **A6. Run-fusion theory (mirror A1 for runs).** Repeat the A1 analysis for
      the run-aware *run-fusion* step — collapse `u^k` to a flat `(u^k)` — rather
      than for a pair merge: (i) prove it always reduces `CS` (the analogue of
      `Δ ≤ 0`); (ii) decide whether `Δ = 0` in the genuine-Markov case, as A1 did
      for pairs. *Looks harder than the pair case.* One step replaces a whole run
      **and all run lengths at once** (several new words, one per length), so
      there is no single `(u,v)` pair to hang the `A(x) / B(y) / Q` context
      split on; the effect is the removal of the `k−1` internal `(u,u)`
      self-loops plus the two new boundary bigrams at the run's ends, all
      interacting through one new word each with its own in/out edges. Likely
      the right handle is the conditional-entropy form (`TREE_WORDS.md` §7)
      rather than the `m`-factorisation, since run-fusion moves `N(u)` and
      `N(u,u)` together. *Status: empirical only* — `check_run_aware`
      (`docs/TREE_WORDS.md` §9.1) finds `0` positive `Δ` over `41 167` enumerated
      steps, with a heavier cross-check (`118 597` corpora × ≤40 steps; `4 000`
      random run-heavy corpora × ≤60 steps) also clean; a symbolic proof and the
      `Δ = 0`-under-Markov question are open.

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
- [x] **C4. "Breaking open the pair" prior.** For an unobserved `(uv)w`, seed the
      count from the observed `vw` (recursively); when both words are pairs,
      break the later (rarer) one; base case = single characters.
      *Detail + feasibility pass done* in `docs/BREAK_OPEN_PRIOR.md`: the
      estimation rule `M_ref(a,b) = N(a,b) + alpha·P(break(a,b))`, where
      `break(a,b)` opens the **later** word (by wordlist order, so no ties) to
      its boundary child; `P` is defined by building `M` **bottom-up** in
      `NUM_PAIRS` order (so normalisation exists when needed), with `P_mar`
      only at the character base case.  Feasibility table on `tw2040`: right
      child JS 0.471 vs independence 0.508 vs left child 0.642.  Verdict:
      plausible but modest; **not yet wired in** — judge by held-out likelihood
      (`choose_kappa.py`) before adopting.
- [ ] **C5. Implement the bottom-up `M` construction (break-open prior).**
      Code the algorithm of `docs/BREAK_OPEN_PRIOR.md` §4 and **validate on
      held-out data** (the `choose_kappa.py` binomial-thinning protocol, scoring
      `M_ref` against test counts — compare the break-open prior with the
      independence `P_mar`, at `tw96`/`tw512`/`tw2040`, and re-sweep `kappa`).
      Details to settle on the way:
      * **`M_ref(w,w)` — settled: `alpha·P(v,u)`.**  Both endpoints of the
        self-loop are the *same* word `w = (uv)`, so "break the later word" is
        undefined; breaking one side but not the other would be asymmetric.
        Break **both** ends, giving the internal junction
        `(rc(w), lc(w)) = (v, u)`.  (This also matches the observed self-loop
        term: `Q = N(u,v,u,v)` sits at the `v→u` junction.)  The alternatives
        "break only the left" (`P(v,w)`, via `N(v,(uv))`) or "only the right"
        (`P(w,u)`, via `N((uv),u)`) are rejected as asymmetric.
      * **Decrement: subtract `N` or `M`?** — count changes are `N`; a cell's
        prior is frozen at creation and survives a mere count decrement, but a
        cell that becomes *structurally impossible* is zeroed outright.  So
        decrement `N`, zero a dead cell's `M`.
      * **`alpha`, and does it depend on `NUM_PAIRS`?** — the prior mass per
        cell (or per row/column); whether one `alpha` transfers across levels or
        must shrink as words are added (each new word adds a row and a column).
      * **Run words — `k`-ary, `lc = rc = u`.**  A flat run word `(u^k)` is a
        single **`k`-ary** merge of `k` copies of `u` (one word per length, per
        A2), *not* `k−1` nested binary merges.  Hence `lc((u^k)) = rc((u^k)) = u`;
        breaking it once drops to `u`, and its self-loop prior is `alpha·P(u,u)`.
        The dictionary is run-aware throughout (C6), so C5 sees run words only.
      * **Dead cells** — after `(uv)` is added, `M(u,v)` must be exactly **zero**
        (structural: no tokenised string has `u` then `v`).  Resolved in
        `BREAK_OPEN_PRIOR.md` §4 ("Where the dead cell's mass goes"): the
        observed `N(u,v)` is *absorbed by the new word* (it becomes row/column
        `w`, i.e. the tokens the merge deletes); the prior is *re-expressed* on
        the new word (row `w` from `P(v,·)`, column `w` from `P(·,u)`), not
        conserved.  So "prior frozen at creation" holds only until a cell is
        structurally invalidated.

- [ ] **C6. Re-run C1–C3 with the run-aware dictionary (this is C5's
      baseline).**  Make the run-aware rule (`(u^k)`, A2) the **only** dictionary
      in `scripts/tree_words.py`; the plain pair-merge version is obsolete and
      all records of it (outside git history) are removed.  Regenerate the
      `tw*` artifacts and the held-out 64/128-bit table and rewrite
      `docs/WORD_COMPRESSIBILITY.md` on the run-aware rule.  Its results are the
      **baseline that C5 is compared against**.

## Housekeeping / deferred regenerations

- [x] **H1. Rebuild `work/*/pair_stats.txt` and `pair_factors_L*.npy`** with the
      raised `randomized_svd` `n_iter=8` default — done 2026-10-30,
      `work/afk_pairmatrix.sh`, log `work/afk_pairmatrix.log`
      (all 5 `PAIR_THRESHOLDS`, ~15 s each).
- [ ] **H2. Corpus hardening** (deferred, optional): Ruby heredoc markers /
      UUID fixtures.

## Decisions

- D1. New-doc name + how much of `ADJACENCY_MODEL.md` folds into it. — *past*
  (settled by `ADJACENCY_MATRIX.md`).
- D2. Which `NUM_PAIRS` values to prototype. — *past* (`tw96`/`tw512`/`tw2040`).
- D3. Held-out sample size / training-split policy for C3. — *past* (the 9:1
  interleaved split, `split_corpus.py`).
- D4. Whether C4's prior sits inside C2 or stays separate. — **this is the
  question studied by C5**: the break-open prior as a *replacement for* the
  independence `P_mar` inside the counting prior, judged against the C6
  baseline on held-out data.

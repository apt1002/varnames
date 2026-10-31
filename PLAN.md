# Plan — parallel lines of research

Living index of the open threads. Each line gets a one-line status and a
pointer to the document that owns it. `[ ]` = open, `[~]` = in progress,
`[x]` = done.

This file records **execution status and success/failure only** — the design
notes and the results live in the experiment reports (`docs/*.md`), which the
lines below point to. Plan identifiers (`A1`, `B1`, `C5`, …) are local to this
document: reports and filenames refer to experiments by *name*, never by these
labels (see `README.md`).

## Standing background (done, load-bearing)

- [x] Corpus build + case normalisation — `docs/CORPUS.md`,
      `docs/CASE_NORMALISATION.md`.
- [x] Character-level fixed-budget compressibility — `docs/CODE_LENGTHS.md`.
- [x] Prefix/suffix adjacency model, low-rank + reversal symmetry —
      `docs/ADJACENCY_MODEL.md`.
- [x] Square-root (Hellinger) factorisation + unobserved-pairs counting fix —
      `docs/HELLINGER_FACTORISATION.md`.
- [x] Choosing `k` and `N` for the model size — `docs/CLUSTER_SIZE_STUDY.md`.
- [x] Dictionary (pair-merge) model: CS identity, per-merge delta —
      `docs/TREE_WORDS.md`, `scripts/check_merge_delta.py`.
- [x] Typical run lengths of the corpus — `docs/RUN_LENGTHS.md`,
      `scripts/run_lengths.py`.

## A. Dictionary / pair-merge theory (`docs/TREE_WORDS.md`)

- [~] **A1. Prove `Δ < 0` exactly.** *In progress.* Leading-order proof,
      exact entropy form and an exhaustive numerical sign check are done; the
      exact `ΔS2 ≤ ΔS1` step is still open. `scripts/check_merge_delta.py`.
- [x] **A2. Relax "no threefold repetition"** (run-aware rule). *Succeeded* —
      sign-safe; `docs/TREE_WORDS.md` §9.1.
- [x] **A3. Greedy alternative** (largest `Δ` vs most frequent pair).
      *Succeeded: the frequency rule is the robust proxy.*
      `docs/DICTIONARY_RULES.md`.
- [x] **A4. `(uv)` vs `(u^n)` crossover.** *Succeeded* — the run-aware rule
      wins whenever there is run mass; `docs/DICTIONARY_RULES.md`.
- [x] **A5. Rewrite `TREE_WORDS.md` for pedagogy.** *Done.*
- [ ] **A6. Run-fusion theory** (mirror A1 for runs). *Empirical only* — a
      symbolic proof and the `Δ = 0`-under-Markov question are open.
      `docs/TREE_WORDS.md` §9.1.

## B. Adjacency matrix construction

- [x] **B1. Canonical `docs/ADJACENCY_MATRIX.md`** (how to build the matrix,
      choice of `κ`). *Done* — the experiment docs refer to it.

## C. Apply the dictionary model to `merged.txt`

- [x] **C1. Word × word adjacency counts** (run-aware tokenisation).
      *Done* — `scripts/tree_words.py train`.
- [x] **C2. Fill unobserved adjacencies** with the `κ` prior.
      *Done* — `scripts/tree_words.py score`; best `κ` in
      `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C3. Held-out compressibility.** *Succeeded* — the word model wins at
      equal dictionary size; `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C4. "Breaking open the pair" prior** — design + feasibility pass.
      *Plausible but modest; adopted only if it wins held-out likelihood*
      (resolved by C5). `docs/BREAK_OPEN_PRIOR.md`.
- [x] **C5. Bottom-up `M` construction (break-open prior).** *FAILED — the
      prior LOSES to `P_mar` at every size and `κ`; not adopted.*
      `docs/BREAK_OPEN_PRIOR.md` §8, `scripts/break_open_prior.py`.
- [x] **C6. Re-run C1–C3 on the run-aware dictionary** (C5's baseline).
      *Done* — `docs/WORD_COMPRESSIBILITY.md`.
- [x] **C7. Smooth the break-open shape, or drop it.** *DROPPED (not needed).*

## Housekeeping / deferred regenerations

- [x] **H1. Rebuild `work/*/pair_stats.txt` and `pair_factors_L*.npy`** with the
      raised `randomized_svd` `n_iter=8` default. *Done* — all 5
      `PAIR_THRESHOLDS`; log `work/afk_pairmatrix.log`.
- [ ] **H2. Corpus hardening** (deferred, optional): Ruby heredoc markers /
      UUID fixtures.

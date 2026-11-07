# Productisation — design intent and scope

Status: **draft / long-term horizon — not started.** This note records the
*stable* design intent, scope and audiences for turning the research into a
standard and a pair of implementations. It is not an experiment report: the
research lines that feed it are section E of `PLAN.md`, and the supporting
results live in the reports those lines point to. Adapt freely as the research
settles — only the items marked **settled** should be treated as constraints.

## Goal

A **language-neutral standard**: a bijection between identifiers and integers,
defined for two fixed sets — the **64-bit** set and the **128-bit** set — with
published lookup tables.

## Encoding (settled intent)

- **Little-endian** bit/byte order.
- **Stop token coded as zeros, beyond the target length.** The stop symbol's
  codeword is all-zero bits, and it may sit *beyond* the target compressed
  length (64 or 128 bits): a target-length code is zero-padded, so an identifier
  shorter than the budget never reaches the stop. (Exact framing/termination
  still to be worked out.)

## Scope

In scope:

- the bijection and the 64-/128-bit sets;
- deciding how to publish the lookup tables;
- the standardised tables as the default, with **non-standard tables allowed**.

Out of scope (explicit):

- **falling back to a hash function** for identifiers that do not fit — out of
  scope in both implementations;
- the table-building tools need **not** be language-neutral.

## Deliverables

1. **Write-up of the best algorithm** — corpus, case normalisation, word list,
   tokenisation, adjacency matrix, clustering, encoding.
2. **Write-up of rejected alternatives** — reframed as justification for the
   design decisions (the data already exists; this is narrative).
3. **Ablation study** (design TBD).
4. **64-/128-bit set study** — what fraction of real identifiers fit; the
   longest compressed length that fits vs the shortest uncompressed length that
   does not; a generative view of what random identifiers look like.
5. **Standard proposal** — the language-neutral bijection, the two sets, and
   the table publication scheme.
6. **Python reference implementation** — runnable, readable.
7. **Rust engineering implementation** — runnable, readable.
8. **Table-building tools** — easy to use and modify.
9. **Licence** (settled) — `MIT OR Apache-2.0` for code and specification,
   `CC0-1.0` for the corpus and the published tables; see `README.md`.

Both implementations (6, 7) default to the standardised tables but accept
non-standard tables.

## Audiences

- **Python reference** — people porting the library.
- **Rust** — people writing compilers.

## Open questions / dependencies

- How much of the full-table → co-clustered loss is avoidable, and whether the
  matrix needs direct compression, determine whether the encoding targets
  (64/128 bits) are achievable — see the plan's cluster-loss and
  matrix-compression lines.
- The fit fraction depends on the real-world identifier distribution, which the
  64-/128-bit set study (deliverable 4) must measure rather than assume.

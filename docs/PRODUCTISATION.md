# Productisation — audiences, artefacts, and what is left

**Status: built; not yet published.** The standard, the tables and both
implementations exist and agree with one another; what remains is publication
(the crate, the wheel, the sdist), not design. Research progress is *not*
recorded here — `PLAN.md` is the index of threads and their status, and each
report it points to owns the detail. This note changes when the **product**
changes: a new audience, a new artefact, or a promise we start or stop making.

## The product

One standard, one model file, two implementations.

* **The standard** ([`STANDARD.md`](../standard/STANDARD.md), version 0.1) —
  a bijection between identifiers and integers, with two fixed budgets, 64 and
  128 bits, and conformance rules for encoders, decoders and model files.
* **The model** ([`model.nvm1`](../standard/model.nvm1), 30,745 bytes) — 63
  characters, 8,128 pair-merge words, 32 right clusters. Its format is
  [`MODEL_FORMAT.md`](../standard/MODEL_FORMAT.md), whose nine invariants a
  reader must check. `model.yaml` is the same model in readable form.
* **The code** — a reference implementation in [`python/`](../python/) and an
  engineering implementation in [`rust/`](../rust/). Both load any conforming
  model file; both default to the shipped one.
* **The builder** — [`scripts/build_tables.py`](../scripts/build_tables.py),
  one command from a corpus to a `model.nvm1`; run over the shipped corpus it
  reproduces the shipped file byte for byte, digest and all
  ([`BUILDING.md`](BUILDING.md)).

The measured operating point is **45.2 bits** per held-out identifier,
**85.0 %** of them in 64 bits and **99.0 %** in 128 bits, for a 30,745-byte
model (32.8 kB counting the library). The numbers and their measurement are in
[`BUDGET64_STUDY.md`](BUDGET64_STUDY.md) and
[`MODEL_BUDGET.md`](MODEL_BUDGET.md).
A 64-bit code still rejects about one identifier in six, and that fraction, not
the mean bit count, is the number to price changes against.

The code and the specification are offered under **MIT OR Apache-2.0**; the
derived corpus and the published tables under **CC0-1.0**. The split is
deliberate: the tables are data that an implementation is expected to embed, so
they must not carry an attribution burden. See "Licensing" in
[`README.md`](../README.md).

## Audiences

Four kinds of user, each with a different entry point. The gaps listed are the
honest ones; there is no fifth audience waiting on a feature we have not built.

### 1. Consumers of the Python library

They want `pip install varnames`, an object they can share between threads, and
no surprises in the API.

**Ships:** the package, its console script `varnames` and `python -m varnames`;
the standard tables inside the package with their SHA-256 checked at load;
`Codec`, `Model`, `standard()` and the `case` module; the 250 golden vectors as
a test; annotations and `py.typed`; a test suite whose held-out rate test
reproduces the figure above. The API and the reliability promises are in
[`python/README.md`](../python/README.md).

**Not yet:** it is on no index — PyPI has not been published to. The package
version is 0.1.0, and until 1.0 a minor version may change the API.

### 2. Consumers of the Rust library

They want a crate with no build script, no dependencies and no data files at
run time, and an MSRV they can name.

**Ships:** the crate with the standard tables compiled in and digest-checked, a
CLI that mirrors the Python one, typed indices for the model tables, rustdoc on
every public item, and MSRV 1.85 (what Debian stable ships). `Codec` holds an
`Arc<Model>`, so cloning is an increment and the tables are parsed once. See
[`rust/README.md`](../rust/README.md).

**Not yet:** crates.io has not been published to; rustdoc hosting on docs.rs
follows from that publication, and needs nothing from us.

### 3. People building their own model

They have a corpus — another language's identifiers, or a different
alphabet — and want a model file, without changing the file format or either
implementation.

**Ships:** [`BUILDING.md`](BUILDING.md), one command, and a stage-by-stage
price of what it costs; the output is an ordinary `.nvm1` file, which both
implementations already accept, and a `model.yaml` for reading and diffing. A
different corpus makes a *custom* model in the sense of §9 of the standard: a
different file and digest, which is exactly how a deployment detects that it is
not on the standard.

**Not yet:** nothing blocking. The builder needs Python 3 and `numpy`; that
dependency belongs to the tools and is stated in `BUILDING.md`, not to the
published `varnames` package, which does not import `numpy` and must not
declare it. A corpus and the memory to cluster it are the builder's own.

### 4. People working on the tools, or defining another model

They want the format precisely stated, an oracle to test against, and the
freedom to replace the tables.

**Ships:** the format and its invariants
([`MODEL_FORMAT.md`](../standard/MODEL_FORMAT.md)); the conformance rules and
the custom-model route of [`STANDARD.md`](../standard/STANDARD.md) §§8–9;
250 golden vectors with exact integers and bit lengths; two independent readers
that must agree on all of them; and [`check.sh`](../check.sh), which asserts
the table digests, the byte identity of the packaged copies, both suites and
the vector count in one command.

**Not yet:** there is no third conformance harness beyond `golden.txt` and the
two readers — a third implementation can use the file, but we do not ship a
standalone checker. There is no version negotiation beyond the magic: a
breaking change to the format is `NVM2`, and a reader rejects a magic it does
not know.

## What the product deliberately does not do

The standard's §10 is the authority; in one line each:

* no hash fallback for names that do not fit — the sets are defined by
  exclusion, and a fallback belongs to a transport;
* encoding normalises nothing — case convention is the caller's, §11 being an
  optional conversion;
* no rule about what an identifier *is*, or about Unicode normalisation;
* table-building is not specified, only its output;
* the model file is not itself compressed.

## What publication still needs

A short list, in order:

1. Publish the crate (`cargo publish` from `rust/`), which also puts the
   rustdoc on docs.rs.
2. Publish the package (`python -m build` and upload from `python/`), wheel and
   sdist. Each package directory carries its own three licence texts, so the
   archives are complete on their own; the PEP 639 metadata records the code's
   `License-Expression: MIT OR Apache-2.0` and puts all three files in the
   wheel's `dist-info/licenses/`.
3. Tag 0.1.0 in git and check that the version appears identically in
   `rust/Cargo.toml`, `python/pyproject.toml` and `python/varnames/__init__.py`.
4. Run `./check.sh` on the tagged tree: table digests, packaged copies, both
   suites and the 250 vectors.

The repository is <https://github.com/apt1002/varnames>; the names `varnames`
appeared free on both indexes when this note was written.

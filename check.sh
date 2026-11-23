#!/bin/sh
# The repository's one check: both implementations, and the published files.
#
# It is a procedure and a policy statement.  The policy is that the two
# implementations agree with the published tables, with `standard/golden.txt`
# and with each other, and that neither is allowed to drift from the files that
# define the standard.  Nothing here needs `make`; run it from anywhere:
#
#     ./check.sh
#
# Exit status is 0 only if every step passed.  It needs `python3` (3.9 or later)
# and `cargo`; the Python package itself has no dependencies, and the Rust crate
# has none either.
set -eu

cd "$(dirname "$0")"

STEP=0
step() {
    STEP=$((STEP + 1))
    printf '\n=== %d. %s\n' "$STEP" "$1"
}

die() {
    printf 'check.sh: %s\n' "$1" >&2
    exit 1
}

# ---------------------------------------------------------------------------
step "the published tables are the files the implementations ship"

MODEL_SHA=976670d71a1273a2506bb537183c4854523bec20eb0b2c9708b5934adbef3f79
PAIRS_SHA=fe4f29facc43e72b8bd263a31712013d58b3a0b29acce595b05a5cf0134f972c
GOLDEN_SHA=bf2481b8acf2c941b8413ca37b591e83e7ba9820f187d44d62b385faf178ccb9

digest=$(sha256sum standard/model.nvm1 | cut -d' ' -f1)
[ "$digest" = "$MODEL_SHA" ] ||
    die "standard/model.nvm1 has SHA-256 $digest, published $MODEL_SHA"

digest=$(sha256sum standard/case-pairs.txt | cut -d' ' -f1)
[ "$digest" = "$PAIRS_SHA" ] ||
    die "standard/case-pairs.txt has SHA-256 $digest, published $PAIRS_SHA"

digest=$(sha256sum standard/golden.txt | cut -d' ' -f1)
[ "$digest" = "$GOLDEN_SHA" ] ||
    die "standard/golden.txt has SHA-256 $digest, published $GOLDEN_SHA"

for copy in python/varnames/data/model.nvm1 rust/data/model.nvm1; do
    cmp -s standard/model.nvm1 "$copy" ||
        die "$copy is not byte-for-byte standard/model.nvm1"
done

for copy in python/varnames/data/case-pairs.txt rust/data/case-pairs.txt; do
    cmp -s standard/case-pairs.txt "$copy" ||
        die "$copy is not byte-for-byte standard/case-pairs.txt"
done

# Each package archive contains only its own directory, so its licence texts
# must be copies of these, not links out of it.
for name in MIT APACHE CC0; do
    for copy in python/LICENSE-$name rust/LICENSE-$name; do
        cmp -s LICENSE-$name "$copy" ||
            die "$copy is not byte-for-byte LICENSE-$name"
    done
done

echo "model, pairs and licences: shipped twice, identical"

# ---------------------------------------------------------------------------
step "the Python reference implementation"

(
    cd python
    python3 -m unittest discover -s tests
)
echo "python: reference suite passed"

# ---------------------------------------------------------------------------
step "the Rust engineering implementation"

if ! command -v cargo >/dev/null 2>&1; then
    die "cargo is not installed: both implementations are part of this check"
fi
(
    cd rust
    cargo test --quiet --all-targets
)
echo "rust: engineering suite passed"

# ---------------------------------------------------------------------------
step "the two implementations agree"

# Both suites read `standard/golden.txt` and check every vector against their
# own codec, so agreement is transitive through that file.  This step re-checks
# that the file has the vectors the standard advertises, so that a suite cannot
# pass by checking nothing.
vectors=$(grep -c '^[^#]' standard/golden.txt || true)
[ "$vectors" = "250" ] ||
    die "standard/golden.txt has $vectors vectors, the standard publishes 250"
echo "golden.txt: $vectors vectors, decoded by both implementations"

printf '\ncheck.sh: all %d steps passed\n' "$STEP"

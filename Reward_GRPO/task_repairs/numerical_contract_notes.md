# Numerical task corrections and unresolved contracts

Source: Aider-AI/polyglot-benchmark
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`, C++ practice exercises.
These are task-version changes; final admission must reauthenticate every changed
protected asset and rerun both the official and topic verifiers.

## Complex Numbers

The `double` API specifies complex division and magnitude without a small-input
restriction. Finite components such as `3e200, 4e200` have representable magnitude
`5e200`; scaling both operands of a division by the same nonzero finite factor
does not change the quotient. The old intermediate squaring overflowed or
underflowed at `1e200` and `1e-200`.

The reference uses `hypot` for magnitude and power-of-two scaling for division.
Official tests and existing topic groups enforce finite scaled magnitude, direct
division and both scalar division orderings. Comparisons normalize the magnitude
before applying the existing 0.005 tolerance; no tighter precision, algorithm,
nonfinite-input or zero-denominator requirement is introduced.

The topic controls restore each old failure independently: naive magnitude,
naive complex division and naive scalar division must fail. The alternative
positive control uses the conjugation identity for scalar division and remains
valid at both scales. This correction establishes reference health and coverage;
it does not claim a new model score.

## D&D Character: reference corrected, training held

`rand()` has an inclusive maximum. The old integer bucket division could return
7 for the final incomplete bucket. Rejection sampling now discards that tail
before mapping equal-sized buckets onto faces 1 through 6.

A reference-only regression wraps `rand` at link time to force every bucket's
endpoints and each rejected tail value, then checks four-roll/drop-lowest sums.
The old mapping fails deterministically. This does not prescribe a candidate RNG
or add a statistical test to the official exercise.

The pinned contract explicitly requires random four-dice generation. Existing
candidate probes enforce ranges, modifiers and hitpoints; the constant-ability
control intentionally passes those checks and emits a diagnostic. Finite output
sampling cannot establish random generation deterministically without excluding
valid random sequences or prescribing a new injectable RNG API. Consequently the
task must remain excluded from full-correctness GRPO admission until a versioned,
contract-supported deterministic randomness test interface is established. The
range correction alone is not sufficient for training admission.

## Grade School: training held, assets unchanged

The pinned instructions prohibit adding a student twice to a grade or the roster
and require an indication that the addition is incorrect. Its C++ API is
`void school::add(std::string const&, int)`; neither instructions nor the eight
official tests specify an exception, status accessor, return value or other
rejection signal. The reference inserts duplicates. No precise rejection
mechanism can be inferred from the authenticated version.

Do not silently choose an exception type or redefine rejection as a no-op.
Admission is blocked pending an explicit versioned contract/API decision and
corresponding reference/tests. Existing unique-student coverage remains useful
but does not prove the full documented contract.

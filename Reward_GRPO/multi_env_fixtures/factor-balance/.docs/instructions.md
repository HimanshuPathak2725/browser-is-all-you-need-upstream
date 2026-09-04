# Factor balance

Implement the functions in `factor_balance.h` and `factor_balance.cpp`.
`proper_factor_sum(n)` returns the sum of all positive divisors of `n`
strictly smaller than `n`. `classify(n)` returns `light` when that sum is
smaller than `n`, `equal` when it is equal, and `heavy` when it is
larger. Both functions throw `std::domain_error` for non-positive input.
`classify_range(first, last)` classifies every integer in the inclusive
range; it returns an empty vector when `first > last` and otherwise inherits
the same invalid-input rule.

The implementation must handle repeated divisor pairs correctly, including
perfect squares. Return complete whole-file listings for both editable files.

# Partial Tree Proof

Build and verify deterministic partial binary-tree proofs with duplicate-last padding, exact payload consumption, selected-leaf binding, and expected-root validation.

## Public API

```cpp
partial_tree::build and partial_tree::verify
```

## Files you may edit

- `partial-tree-proof.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

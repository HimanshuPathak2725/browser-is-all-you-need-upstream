# Structural Bundle Registry

Intern leaf, ordered-pair, fold, and transparent tag nodes so structurally equal values reuse handles while flattening preserves left-to-right leaf order.

## Public API

```cpp
class structural_bundles::Registry
```

## Files you may edit

- `structural-bundle-registry.h`
- `structural-bundle-registry.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

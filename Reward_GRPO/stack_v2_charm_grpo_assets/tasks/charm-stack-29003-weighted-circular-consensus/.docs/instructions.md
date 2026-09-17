# Weighted Circular Consensus

Compute a weighted circular mean on an arbitrary period/origin, normalize to a half-open interval, and reject weak or undefined resultants.

## Public API

```cpp
circular_consensus::consensus
```

## Files you may edit

- `weighted-circular-consensus.h`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

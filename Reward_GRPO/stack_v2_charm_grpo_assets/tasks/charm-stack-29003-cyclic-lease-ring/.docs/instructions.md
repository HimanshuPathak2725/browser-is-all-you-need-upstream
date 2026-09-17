# Cyclic Lease Ring

Acquire free slots from a cyclic cursor, track reuse generations and monotone acquisition epochs, and retire all leases through an epoch.

## Public API

```cpp
class lease_ring::Ring
```

## Files you may edit

- `cyclic-lease-ring.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

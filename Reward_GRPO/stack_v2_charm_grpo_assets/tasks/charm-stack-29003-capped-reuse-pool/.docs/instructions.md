# Capped Reuse Pool

Manage generation-stamped handles with delayed retirement and a bounded circular collection scan while always acquiring the lowest free slot.

## Public API

```cpp
class reuse_pool::Pool
```

## Files you may edit

- `capped-reuse-pool.h`
- `capped-reuse-pool.cpp`
- `capped-reuse-pool-policy.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

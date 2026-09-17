# Coalescing Range Allocator

Allocate aligned regions using deterministic best fit, retain alignment prefixes/suffixes, and transactionally release and coalesce adjacent free space.

## Public API

```cpp
class range_allocator::Allocator
```

## Files you may edit

- `coalescing-range-allocator.h`
- `coalescing-range-allocator.cpp`
- `coalescing-range-policy.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

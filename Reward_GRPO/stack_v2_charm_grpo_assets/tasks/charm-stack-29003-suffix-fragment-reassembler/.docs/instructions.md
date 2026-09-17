# Suffix Fragment Reassembler

Accept offset fragments transactionally, reject conflicting overlap, and emit only bytes newly unlocked at the contiguous prefix.

## Public API

```cpp
class suffix_reassembly::Reassembler
```

## Files you may edit

- `suffix-fragment-reassembler.h`
- `suffix-fragment-reassembler.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

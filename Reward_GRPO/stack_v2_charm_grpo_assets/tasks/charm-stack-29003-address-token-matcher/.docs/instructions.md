# Address Token Matcher

Match typed address queries as ordered subsequences while preserving word/number kinds, number adjacency constraints, case-insensitive words, and stable candidate order.

## Public API

```cpp
address_tokens::match
```

## Files you may edit

- `address-token-matcher.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

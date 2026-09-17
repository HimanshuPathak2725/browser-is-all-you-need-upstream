# Biunique Code Dictionary

Maintain a transactional one-to-one code/name dictionary with idempotent reinsertion, name-first parsing, strict signed decimal fallback, and stable formatting.

## Public API

```cpp
class code_dictionary::Dictionary
```

## Files you may edit

- `biunique-code-dictionary.h`
- `biunique-code-dictionary.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

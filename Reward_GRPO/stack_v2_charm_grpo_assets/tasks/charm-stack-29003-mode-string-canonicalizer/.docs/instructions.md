# Mode String Canonicalizer

Parse one base mode and unique unordered modifiers, validate compatibility, and serialize the canonical semantic order +, b, x, e.

## Public API

```cpp
mode_string::parse and mode_string::canonical
```

## Files you may edit

- `mode-string-canonicalizer.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

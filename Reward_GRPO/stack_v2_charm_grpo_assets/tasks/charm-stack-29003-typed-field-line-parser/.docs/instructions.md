# Typed Field Line Parser

Parse semicolon-separated key/value fields with strict keys, quoted escapes, full-token primitive recognition, duplicate rejection, and exact error offsets.

## Public API

```cpp
typed_fields::parse_line
```

## Files you may edit

- `typed-field-line-parser.h`
- `typed-field-line-parser.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

# Hilbert Cell Codec

Implement a header-only bijection between square grid coordinates and Hilbert traversal indices for orders 0 through 31.

## Public API

```cpp
hilbert_cells::encode and hilbert_cells::decode
```

## Files you may edit

- `hilbert-cell-codec.h`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

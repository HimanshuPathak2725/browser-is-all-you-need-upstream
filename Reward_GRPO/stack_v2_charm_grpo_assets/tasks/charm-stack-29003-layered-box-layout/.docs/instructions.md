# Layered Box Layout

Lay out positive-sized named boxes by ascending layer, preserve declaration order within each layer, center rows using floor division, and detect invalid or overflowing geometry.

## Public API

```cpp
layered_boxes::arrange
```

## Files you may edit

- `layered-box-layout.h`
- `layered-box-layout.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

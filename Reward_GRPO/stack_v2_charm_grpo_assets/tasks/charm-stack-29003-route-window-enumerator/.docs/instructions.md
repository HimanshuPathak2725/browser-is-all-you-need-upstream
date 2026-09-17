# Route Window Enumerator

Enumerate simple start-to-terminal routes in declared edge order while charging only true branching against a budget; preserve distinct paths even when their concatenated labels are equal.

## Public API

```cpp
route_windows::enumerate
```

## Files you may edit

- `route-window-enumerator.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

# Grid Neighbor Topology

Map checked 3-D grid coordinates to stable row-major IDs and return in-bounds orthogonal neighbors in the documented axis order.

## Public API

```cpp
class grid_topology::Grid
```

## Files you may edit

- `grid-neighbor-topology.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

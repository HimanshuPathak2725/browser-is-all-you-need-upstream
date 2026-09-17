# Planar Motion Lock Transition

Clamp a planar displacement by Euclidean length, then lock a strictly smaller axis when it is at or below a configurable ratio of the dominant axis.

## Public API

```cpp
motion_lock::constrain
```

## Files you may edit

- `planar-motion-lock-transition.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

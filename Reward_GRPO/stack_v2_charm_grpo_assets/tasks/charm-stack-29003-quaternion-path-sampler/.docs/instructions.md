# Quaternion Path Sampler

Validate time-ordered quaternion keys and sample normalized shortest-arc orientations with clamping and stable query-order behavior.

## Public API

```cpp
quaternion_path::sample and quaternion_path::sample_many
```

## Files you may edit

- `quaternion-path-sampler.h`
- `quaternion-path-sampler.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

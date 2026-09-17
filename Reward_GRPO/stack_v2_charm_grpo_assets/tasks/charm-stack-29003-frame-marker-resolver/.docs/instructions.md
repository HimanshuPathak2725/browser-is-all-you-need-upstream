# Frame Marker Resolver

Advance across positive-duration animation frames with loop or clamp semantics and report markers crossed at frame-start events in timeline order.

## Public API

```cpp
frame_markers::advance and frame_markers::find_frame
```

## Files you may edit

- `frame-marker-resolver.h`
- `frame-marker-resolver.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

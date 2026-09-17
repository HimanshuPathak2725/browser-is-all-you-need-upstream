# Quorum Segment Assembler

Assemble fixed-width indexed segments after two matching observations among at most three per segment; newer generations reset state and completed generations publish once.

## Public API

```cpp
class quorum_segments::Assembler
```

## Files you may edit

- `quorum-segment-assembler.h`
- `quorum-segment-assembler.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

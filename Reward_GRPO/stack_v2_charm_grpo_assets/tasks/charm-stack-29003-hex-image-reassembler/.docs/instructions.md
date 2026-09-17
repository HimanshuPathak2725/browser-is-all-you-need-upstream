# Hex Image Reassembler

Validate and reassemble Intel-HEX-style data, extended-address, and EOF records into sorted coalesced spans with conflict-safe overlaps.

## Public API

```cpp
hex_image::reassemble
```

## Files you may edit

- `hex-image-reassembler.cpp`

Keep the public API source-compatible, use only the C++ standard library, and
produce deterministic behavior. Invalid input described by the API contract
must throw `std::invalid_argument` or `std::out_of_range` as appropriate.
Edit only the files listed above; all other repository files are read-only.

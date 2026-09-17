# Instructions

Your task is to return a square matrix of a given size.

The matrix should be filled with natural numbers, starting from 1 in the top-left corner, increasing in an inward, clockwise spiral order, like these examples:

## Examples

### Spiral matrix of size 3

```text
1 2 3
8 9 4
7 6 5
```

### Spiral matrix of size 4

```text
 1  2  3 4
12 13 14 5
11 16 15 6
10  9  8 7
```


## C++ interface contract

The test file is not shown to you, so the interface it expects is stated here in
full. Implement exactly these names and signatures; the tests use nothing else.

```cpp
namespace spiral_matrix {
std::vector<std::vector<uint32_t>> spiral_matrix(uint32_t size);
}
```

The function has the same name as its namespace; the tests call it as `spiral_matrix::spiral_matrix(n)`. Size 0 returns an empty vector.

## Build environment

- The exercise is compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, so
  any warning fails the build.
- Only `spiral_matrix.h` and `spiral_matrix.cpp` are editable. `CMakeLists.txt` and the test
  file are fixed and must not be modified.
- The test file includes only `spiral_matrix.h`, so every name above must be visible
  from that header.
- You may either declare in `spiral_matrix.h` and define in `spiral_matrix.cpp`, or define
  everything `inline`/in-class in `spiral_matrix.h` and leave `spiral_matrix.cpp` unchanged.
  Both are accepted.

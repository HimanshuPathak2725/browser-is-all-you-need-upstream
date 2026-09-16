# Columnar code

Implement `columnar::normalize` and `columnar::encode` in
`columnar_code.h` and `columnar_code.cpp`.

`normalize` keeps only ASCII letters and digits and lowercases the letters.
`encode(text, columns)` writes the normalized text row by row into the given
number of columns, then emits those columns from left to right. Every emitted
column has the same height; missing cells are represented by `_`, and
columns are separated by one ordinary space. Empty normalized input produces
an empty string. A zero column count throws `std::invalid_argument`.

For example, `encode("abcde", 3)` is exactly `"ad be c_"`.
Return complete whole-file listings for both editable files.

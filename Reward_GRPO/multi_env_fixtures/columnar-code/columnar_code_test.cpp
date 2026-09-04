#include "columnar_code.h"

#include "test/catch.hpp"

#include <stdexcept>

TEST_CASE("normalization keeps lowercase letters and digits") {
    REQUIRE(columnar::normalize("Meet me at 5!") == "meetmeat5");
    REQUIRE(columnar::normalize("A-b_C.d") == "abcd");
}

TEST_CASE("empty and punctuation-only input normalize empty") {
    REQUIRE(columnar::normalize("").empty());
    REQUIRE(columnar::normalize(" -!? ").empty());
}

TEST_CASE("documented transposition is exact") {
    REQUIRE(columnar::encode("abcde", 3) == "ad be c_");
}

TEST_CASE("a rectangular input needs no padding") {
    REQUIRE(columnar::encode("abcdef", 3) == "ad be cf");
}

TEST_CASE("normalization happens before transposition") {
    REQUIRE(columnar::encode("Meet me at 5!", 4) == "mm5 ee_ ea_ tt_");
}

TEST_CASE("one column returns normalized input") {
    REQUIRE(columnar::encode("A b-3", 1) == "ab3");
}

TEST_CASE("more columns than characters produces padded groups") {
    REQUIRE(columnar::encode("ab", 4) == "a b _ _");
}

TEST_CASE("empty normalized input produces no groups") {
    REQUIRE(columnar::encode("!?", 5).empty());
}

TEST_CASE("zero columns is rejected even for empty input") {
    REQUIRE_THROWS_AS(columnar::encode("", 0), std::invalid_argument);
    REQUIRE_THROWS_AS(columnar::encode("abc", 0), std::invalid_argument);
}

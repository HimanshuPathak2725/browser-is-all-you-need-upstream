#include "factor_balance.h"

#include "test/catch.hpp"

#include <stdexcept>
#include <vector>

using factor_balance::balance;

TEST_CASE("one has no proper factors") {
    REQUIRE(factor_balance::proper_factor_sum(1) == 0);
    REQUIRE(factor_balance::classify(1) == balance::light);
}

TEST_CASE("prime numbers are light") {
    REQUIRE(factor_balance::proper_factor_sum(13) == 1);
    REQUIRE(factor_balance::classify(13) == balance::light);
}

TEST_CASE("an equal number is recognized") {
    REQUIRE(factor_balance::proper_factor_sum(28) == 28);
    REQUIRE(factor_balance::classify(28) == balance::equal);
}

TEST_CASE("a heavy number is recognized") {
    REQUIRE(factor_balance::proper_factor_sum(12) == 16);
    REQUIRE(factor_balance::classify(12) == balance::heavy);
}

TEST_CASE("perfect-square divisors are counted once") {
    REQUIRE(factor_balance::proper_factor_sum(16) == 15);
    REQUIRE(factor_balance::proper_factor_sum(36) == 55);
}

TEST_CASE("non-positive values are rejected") {
    REQUIRE_THROWS_AS(factor_balance::proper_factor_sum(0), std::domain_error);
    REQUIRE_THROWS_AS(factor_balance::classify(-4), std::domain_error);
}

TEST_CASE("range classification is inclusive") {
    REQUIRE(factor_balance::classify_range(5, 8)
            == std::vector<balance>{
                balance::light, balance::equal, balance::light, balance::light
            });
}

TEST_CASE("reversed range is empty") {
    REQUIRE(factor_balance::classify_range(4, 3).empty());
}

TEST_CASE("range propagates invalid input") {
    REQUIRE_THROWS_AS(factor_balance::classify_range(0, 2), std::domain_error);
}

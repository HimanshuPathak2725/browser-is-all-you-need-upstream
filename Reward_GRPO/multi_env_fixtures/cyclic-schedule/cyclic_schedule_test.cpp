#include "cyclic_schedule.h"

#include "test/catch.hpp"

using cyclic_schedule::weekly_time;

TEST_CASE("ordinary construction exposes all components") {
    const auto value = weekly_time::at(2, 9, 7);
    REQUIRE(value.weekday() == 2);
    REQUIRE(value.hour() == 9);
    REQUIRE(value.minute() == 7);
    REQUIRE(value.str() == "D2 09:07");
}

TEST_CASE("construction normalizes forward across the week") {
    REQUIRE(weekly_time::at(7, 24, 1) == weekly_time::at(1, 0, 1));
}

TEST_CASE("construction normalizes negative components") {
    REQUIRE(weekly_time::at(0, -1, -1) == weekly_time::at(6, 22, 59));
}

TEST_CASE("advance crosses a day boundary") {
    auto value = weekly_time::at(3, 23, 50);
    REQUIRE(value.advance(20) == weekly_time::at(4, 0, 10));
}

TEST_CASE("advance wraps a complete week") {
    auto value = weekly_time::at(6, 23, 59);
    REQUIRE(value.advance(1) == weekly_time::at(0, 0, 0));
    REQUIRE(value.advance(7 * 24 * 60) == weekly_time::at(0, 0, 0));
}

TEST_CASE("rewind crosses the beginning of the week") {
    auto value = weekly_time::at(0, 0, 5);
    REQUIRE(value.rewind(10) == weekly_time::at(6, 23, 55));
}

TEST_CASE("negative shifts reverse their named operation") {
    auto value = weekly_time::at(4, 12, 30);
    REQUIRE(value.advance(-90) == weekly_time::at(4, 11, 0));
    REQUIRE(value.rewind(-60) == weekly_time::at(4, 12, 0));
}

TEST_CASE("large offsets normalize without iteration") {
    auto value = weekly_time::at(1, 1, 1);
    REQUIRE(value.advance(1000LL * 7 * 24 * 60 + 61)
            == weekly_time::at(1, 2, 2));
}

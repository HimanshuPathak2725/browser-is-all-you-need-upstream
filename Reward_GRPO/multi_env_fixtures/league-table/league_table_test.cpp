#include "league_table.h"

#include "test/catch.hpp"

using league::standing;
using league::table;

TEST_CASE("a new table is empty") {
    const table scores;
    REQUIRE(scores.teams() == 0);
    REQUIRE(scores.points_for("unknown") == 0);
    REQUIRE(scores.standings().empty());
}

TEST_CASE("record creates a team") {
    table scores;
    scores.record("Owls", 3);
    REQUIRE(scores.teams() == 1);
    REQUIRE(scores.points_for("Owls") == 3);
}

TEST_CASE("record accumulates repeated adjustments") {
    table scores;
    scores.record("Owls", 3);
    scores.record("Owls", 4);
    scores.record("Owls", -2);
    REQUIRE(scores.points_for("Owls") == 5);
    REQUIRE(scores.teams() == 1);
}

TEST_CASE("zero-point records still create a team") {
    table scores;
    scores.record("Moles", 0);
    REQUIRE(scores.teams() == 1);
    REQUIRE(scores.points_for("Moles") == 0);
}

TEST_CASE("standings sort points descending") {
    table scores;
    scores.record("Owls", 4);
    scores.record("Moles", 9);
    scores.record("Ants", -1);
    REQUIRE(scores.standings()
            == std::vector<standing>{{"Moles", 9}, {"Owls", 4}, {"Ants", -1}});
}

TEST_CASE("ties sort names ascending") {
    table scores;
    scores.record("Zebras", 6);
    scores.record("Ants", 6);
    scores.record("Moles", 6);
    REQUIRE(scores.standings()
            == std::vector<standing>{{"Ants", 6}, {"Moles", 6}, {"Zebras", 6}});
}

TEST_CASE("returned standings do not mutate the table") {
    table scores;
    scores.record("Owls", 2);
    auto copy = scores.standings();
    copy.front().points = 100;
    REQUIRE(scores.points_for("Owls") == 2);
}

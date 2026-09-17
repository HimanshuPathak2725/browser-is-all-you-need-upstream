#include "robot_name.h"
#ifdef EXERCISM_TEST_SUITE
#include <catch2/catch.hpp>
#else
#include "test/catch.hpp"
#endif
#include <cctype>
#include <string>
#include <unordered_set>

using namespace std;

namespace
{
// Helper function to check the robot name matches the instructions.
//
// 2 uppercase letters followed by 3 digits.
static bool validate_name(const string& name)
{
    if (name.length() != 5)
        return false;
    return isupper(name[0]) && isupper(name[1]) && isdigit(name[2])
        && isdigit(name[3]) && isdigit(name[4]);
}
}

TEST_CASE("has_a_name")
{
    const robot_name::robot robot;

    REQUIRE(validate_name(robot.name()));
}

#if defined(EXERCISM_RUN_ALL_TESTS)
TEST_CASE("name_is_the_same_each_time")
{
    const robot_name::robot robot;

    REQUIRE(robot.name() == robot.name());
}

TEST_CASE("different_robots_have_different_names")
{
    const robot_name::robot robot_one;
    const robot_name::robot robot_two;

    REQUIRE(robot_one.name() != robot_two.name());
}

TEST_CASE("is_able_to_reset_name")
{
    robot_name::robot robot;
    const auto original_name = robot.name();

    robot.reset();

    REQUIRE(original_name != robot.name());
}

TEST_CASE("exhausting_digits_yields_different_names")
{
    robot_name::robot robot;
    unordered_set<string> names;
    names.insert(robot.name());

    for (int i = 0; i < 1000; ++i) {
        robot.reset();
        REQUIRE(names.count(robot.name()) == 0);
        REQUIRE(validate_name(robot.name()));
        names.insert(robot.name());
    }
}

TEST_CASE("reset preserves other live robot identities") {
    robot_name::robot first;
    robot_name::robot second;
    const auto first_original = first.name();
    const auto second_original = second.name();
    first.reset();
    REQUIRE(first.name() != first_original);
    REQUIRE(first.name() != second_original);
    REQUIRE(second.name() == second_original);
    second.reset();
    REQUIRE(second.name() != second_original);
    REQUIRE(second.name() != first.name());
}

#endif

"""Deterministic reference regressions, not candidate RNG requirements."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "Reward_GRPO" / "multi_env_fixtures"


@pytest.mark.parametrize("historical_mapping", [False, True])
def test_reference_six_sided_dice_at_rand_boundaries(tmp_path, historical_mapping):
    """Force inclusive rand endpoints; random sampling almost never finds this bug.

    Link wrapping belongs only to this reference-unit test. A candidate remains
    free to use any RNG; this test is not part of its official task contract.
    """
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("reference regression requires g++")
    fixture = FIXTURES / "dnd-character"
    source = (fixture / ".meta/example.cpp").read_text()
    if historical_mapping:
        start = source.index("int dice_roll() {")
        end = source.index("\nint ability()", start)
        source = source[:start] + (
            "int dice_roll() { return 1 + std::rand() / ((RAND_MAX + 1u) / 6); }\n"
        ) + source[end:]
    (tmp_path / "dnd_character.cpp").write_text(source)
    shutil.copyfile(fixture / ".meta/example.h", tmp_path / "dnd_character.h")
    (tmp_path / "boundary.cpp").write_text(r'''
#include "dnd_character.h"
#include <cstdlib>
#include <initializer_list>
#include <vector>
namespace dnd_character { int dice_roll(); }
static std::vector<int> draws;
static std::size_t next_draw = 0;
extern "C" int __wrap_rand() {
    if (next_draw >= draws.size()) std::abort();
    return draws[next_draw++];
}
static void input(std::initializer_list<int> values) {
    draws = values;
    next_draw = 0;
}
int main() {
    const auto bucket = (static_cast<unsigned long long>(RAND_MAX) + 1) / 6;
    const auto limit = bucket * 6;
    for (int face = 1; face <= 6; ++face) {
        for (auto raw : {(face - 1) * bucket, face * bucket - 1}) {
            input({static_cast<int>(raw)});
            if (dnd_character::dice_roll() != face || next_draw != 1) return 1;
        }
    }
    // glibc's RAND_MAX includes a short seventh bucket; rejection must consume
    // another draw rather than returning 7. Exhaust every rejected endpoint.
    for (auto raw = limit; raw <= static_cast<unsigned long long>(RAND_MAX); ++raw) {
        input({static_cast<int>(raw), 0});
        if (dnd_character::dice_roll() != 1 || next_draw != 2) return 2;
    }
    input({0, static_cast<int>(bucket), static_cast<int>(2 * bucket),
           static_cast<int>(5 * bucket)});
    if (dnd_character::ability() != 11 || next_draw != 4) return 3;
    input({0, 0, 0, 0});
    if (dnd_character::ability() != 3 || next_draw != 4) return 4;
    const auto six = static_cast<int>(limit - 1);
    input({six, six, six, six});
    if (dnd_character::ability() != 18 || next_draw != 4) return 5;
    return 0;
}
''')
    binary = tmp_path / "boundary"
    build = subprocess.run(
        [compiler, "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
         str(tmp_path / "boundary.cpp"), str(tmp_path / "dnd_character.cpp"),
         "-Wl,--wrap=rand", "-o", str(binary)],
        capture_output=True, text=True, timeout=30,
    )
    assert build.returncode == 0, build.stderr
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
    assert result.returncode == (2 if historical_mapping else 0), result.stderr

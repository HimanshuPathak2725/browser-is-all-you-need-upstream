#include "dnd_character.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <numeric>

namespace dnd_character {
int modifier(int score) {
    return std::floor((static_cast<double>(score) - 10) / 2);
}

int dice_roll() {
    // Reject the incomplete bucket in rand()'s inclusive range.
    constexpr auto bucket_size = (static_cast<unsigned long long>(RAND_MAX) + 1) / 6;
    constexpr auto limit = bucket_size * 6;
    unsigned long long draw;
    do {
        draw = static_cast<unsigned long long>(std::rand());
    } while (draw >= limit);
    return 1 + static_cast<int>(draw / bucket_size);
}

int ability() {
    auto rolls = {dice_roll(), dice_roll(), dice_roll(), dice_roll()};
    auto discard = std::min(rolls);

    return std::accumulate(rolls.begin(), rolls.end(), 0) - discard;
}
}  // namespace dnd_character

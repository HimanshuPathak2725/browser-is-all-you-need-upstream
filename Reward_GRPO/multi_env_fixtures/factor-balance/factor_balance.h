#pragma once

#include <vector>

namespace factor_balance {

enum class balance { light, equal, heavy };

int proper_factor_sum(int value);
balance classify(int value);
std::vector<balance> classify_range(int first, int last);

}

#include "factor_balance.h"

#include <stdexcept>

namespace factor_balance {

int proper_factor_sum(int value) {
    if (value <= 0) {
        throw std::domain_error("value must be positive");
    }
    return value - 1;
}

balance classify(int value) {
    const int sum = proper_factor_sum(value);
    return sum == value ? balance::equal : balance::light;
}

std::vector<balance> classify_range(int first, int last) {
    std::vector<balance> result;
    for (int value = first; value <= last; ++value) {
        result.push_back(classify(value));
    }
    return result;
}

}

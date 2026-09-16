#include "factor_balance.h"

#include <stdexcept>

namespace factor_balance {

int proper_factor_sum(int value) {
    if (value <= 0) {
        throw std::domain_error("value must be positive");
    }
    if (value == 1) {
        return 0;
    }
    int sum = 1;
    for (int divisor = 2; divisor <= value / divisor; ++divisor) {
        if (value % divisor != 0) {
            continue;
        }
        sum += divisor;
        const int paired = value / divisor;
        if (paired != divisor) {
            sum += paired;
        }
    }
    return sum;
}

balance classify(int value) {
    const int sum = proper_factor_sum(value);
    if (sum < value) {
        return balance::light;
    }
    if (sum > value) {
        return balance::heavy;
    }
    return balance::equal;
}

std::vector<balance> classify_range(int first, int last) {
    std::vector<balance> result;
    if (first > last) {
        return result;
    }
    for (int value = first; value <= last; ++value) {
        result.push_back(classify(value));
    }
    return result;
}

}

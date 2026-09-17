#include "all_your_base.h"

#include <algorithm>
#include <cstdint>
#include <stdexcept>

namespace all_your_base {

std::vector<unsigned int> convert(unsigned int input_base,
                                  const std::vector<unsigned int>& input_digits,
                                  unsigned int output_base) {
    if (input_base < 2 || output_base < 2)
        throw std::invalid_argument("Invalid base");

    // Accumulate directly in the output radix, least-significant digit first.
    // No integer accumulator has to represent the complete input number.
    std::vector<unsigned int> result;
    for (unsigned int digit : input_digits) {
        if (digit >= input_base)
            throw std::invalid_argument("Invalid number");
        std::uint64_t carry = digit;
        for (auto& output_digit : result) {
            const std::uint64_t value =
                static_cast<std::uint64_t>(output_digit) * input_base + carry;
            output_digit = static_cast<unsigned int>(value % output_base);
            carry = value / output_base;
        }
        while (carry != 0) {
            result.push_back(static_cast<unsigned int>(carry % output_base));
            carry /= output_base;
        }
    }
    std::reverse(result.begin(), result.end());
    return result;
}

}  // namespace all_your_base

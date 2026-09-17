#include "columnar_code.h"

#include <cctype>
#include <stdexcept>

namespace columnar {

std::string normalize(std::string_view text) {
    std::string result;
    for (const char ch : text) {
        const auto value = static_cast<unsigned char>(ch);
        if (std::isalnum(value)) {
            result.push_back(static_cast<char>(std::tolower(value)));
        }
    }
    return result;
}

std::string encode(std::string_view text, std::size_t columns) {
    if (columns == 0) {
        throw std::invalid_argument("columns must be positive");
    }
    const std::string clean = normalize(text);
    if (clean.empty()) {
        return {};
    }
    const std::size_t rows = (clean.size() + columns - 1) / columns;
    std::string result;
    for (std::size_t column = 0; column < columns; ++column) {
        if (column != 0) {
            result.push_back(' ');
        }
        for (std::size_t row = 0; row < rows; ++row) {
            const std::size_t index = row * columns + column;
            result.push_back(index < clean.size() ? clean[index] : '_');
        }
    }
    return result;
}

}

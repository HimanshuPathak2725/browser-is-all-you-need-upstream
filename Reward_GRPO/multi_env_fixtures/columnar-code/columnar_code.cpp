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
    return normalize(text);
}

}

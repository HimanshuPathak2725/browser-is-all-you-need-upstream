#pragma once

#include <cstddef>
#include <string>
#include <string_view>

namespace columnar {

std::string normalize(std::string_view text);
std::string encode(std::string_view text, std::size_t columns);

}

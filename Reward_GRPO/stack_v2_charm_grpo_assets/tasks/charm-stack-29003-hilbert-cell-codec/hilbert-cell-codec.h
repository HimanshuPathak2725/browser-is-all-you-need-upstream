#pragma once
#include <cstdint>
#include <utility>
namespace hilbert_cells {
std::pair<std::uint32_t,std::uint32_t> decode(unsigned order,std::uint64_t index);
std::uint64_t encode(unsigned order,std::uint32_t x,std::uint32_t y);
}

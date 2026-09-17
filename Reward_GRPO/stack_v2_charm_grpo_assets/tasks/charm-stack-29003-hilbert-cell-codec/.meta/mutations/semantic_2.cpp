#include "hilbert-cell-codec.h"
#include <stdexcept>
namespace hilbert_cells {std::pair<std::uint32_t,std::uint32_t> decode(unsigned o,std::uint64_t d){if(o>31)throw std::invalid_argument("order");auto n=std::uint64_t{1}<<o;if(d>=n*n)throw std::out_of_range("index");return{std::uint32_t(d%n),std::uint32_t(d/n)};}std::uint64_t encode(unsigned o,std::uint32_t x,std::uint32_t y){auto n=std::uint64_t{1}<<o;if(x>=n||y>=n)throw std::out_of_range("coordinate");return x*n+y;}}

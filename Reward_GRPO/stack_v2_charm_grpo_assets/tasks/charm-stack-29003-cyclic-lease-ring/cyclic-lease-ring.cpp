#include "cyclic-lease-ring.h"
namespace lease_ring {Ring::Ring(std::size_t n):slots_(n){}std::optional<Lease> Ring::acquire(std::uint64_t){return std::nullopt;}std::size_t Ring::retire_through(std::uint64_t){return 0;}std::size_t Ring::active()const noexcept{return 0;}}

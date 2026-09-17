#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace lease_ring {
struct Lease {std::size_t slot;std::uint64_t generation;bool operator==(const Lease& o)const{return slot==o.slot&&generation==o.generation;}};
class Ring {public:explicit Ring(std::size_t capacity);std::optional<Lease> acquire(std::uint64_t epoch);std::size_t retire_through(std::uint64_t epoch);std::size_t active()const noexcept;private:struct Slot{bool active=false;std::uint64_t epoch=0,generation=0;};std::vector<Slot> slots_;std::size_t cursor_=0,active_=0;std::optional<std::uint64_t> last_epoch_;};
}

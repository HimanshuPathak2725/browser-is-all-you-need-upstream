#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace reuse_pool {
struct Handle{std::size_t index;std::uint64_t generation;bool operator==(const Handle& o)const{return index==o.index&&generation==o.generation;}};
class Pool{public:explicit Pool(std::size_t capacity);std::optional<Handle> acquire();void release(Handle handle);std::size_t collect(std::size_t scan_budget);std::size_t live()const noexcept;private:struct Slot{enum State{free,live,retired}state=free;std::uint64_t generation=0;};std::vector<Slot> slots_;std::size_t cursor_=0,live_=0;};
}

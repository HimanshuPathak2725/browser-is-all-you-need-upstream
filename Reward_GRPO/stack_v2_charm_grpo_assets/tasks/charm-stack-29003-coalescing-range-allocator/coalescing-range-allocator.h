#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace range_allocator {
struct Range{std::size_t offset,size;bool operator==(const Range& o)const{return offset==o.offset&&size==o.size;}};
struct Allocation{std::uint64_t id;std::size_t offset,size;};
class Allocator{public:explicit Allocator(std::size_t capacity);std::optional<Allocation> allocate(std::size_t size,std::size_t alignment);void release(std::uint64_t id);std::vector<Range> free_ranges()const;private:std::vector<Range> free_;std::vector<Allocation> used_;std::uint64_t next_id_=1;};
}

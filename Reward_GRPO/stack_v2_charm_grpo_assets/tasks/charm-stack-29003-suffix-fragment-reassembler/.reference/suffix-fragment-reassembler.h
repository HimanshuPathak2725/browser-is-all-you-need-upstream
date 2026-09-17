#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
namespace suffix_reassembly {
struct Fragment { std::size_t offset; std::vector<std::uint8_t> data; };
class Reassembler {
public:
 explicit Reassembler(std::size_t total_size);
 std::vector<std::uint8_t> accept(const Fragment& fragment);
 std::size_t contiguous_size() const noexcept;
 bool complete() const noexcept;
private:
 std::vector<std::uint8_t> bytes_; std::vector<bool> present_; std::size_t delivered_=0;
};
}

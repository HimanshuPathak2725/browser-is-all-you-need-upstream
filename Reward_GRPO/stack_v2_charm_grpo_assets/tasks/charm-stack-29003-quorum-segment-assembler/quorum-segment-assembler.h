#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace quorum_segments {
class Assembler {
public:
    explicit Assembler(std::size_t segment_count);
    std::optional<std::vector<std::uint8_t>> submit(
        std::uint64_t generation, std::size_t index,
        const std::vector<std::uint8_t>& bytes);
    void reset(std::uint64_t generation);
private:
    struct Slot { std::vector<std::vector<std::uint8_t>> observations; std::optional<std::vector<std::uint8_t>> resolved; };
    std::size_t count_;
    std::optional<std::size_t> width_;
    std::optional<std::uint64_t> generation_;
    std::vector<Slot> slots_;
    bool published_ = false;
    void begin(std::uint64_t generation);
};
}

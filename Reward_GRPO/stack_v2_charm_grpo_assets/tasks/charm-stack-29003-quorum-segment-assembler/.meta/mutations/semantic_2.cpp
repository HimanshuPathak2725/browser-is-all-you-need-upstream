#include "quorum-segment-assembler.h"
#include <stdexcept>
namespace quorum_segments {
Assembler::Assembler(std::size_t n) : count_(n), slots_(n) { if (n == 0) throw std::invalid_argument("segment count"); }
void Assembler::begin(std::uint64_t g) { generation_=g; width_.reset(); slots_.assign(count_, Slot{}); published_=false; }
void Assembler::reset(std::uint64_t g) { if (generation_ && g < *generation_) throw std::invalid_argument("generation"); begin(g); }
std::optional<std::vector<std::uint8_t>> Assembler::submit(std::uint64_t g, std::size_t i, const std::vector<std::uint8_t>& b) {
    if (i >= count_ || b.empty()) throw std::invalid_argument("observation");
    if (generation_ && g < *generation_) return std::nullopt;
    if (!generation_ || g > *generation_) begin(g);
    if (!width_) width_=b.size();
    if (b.size()!=*width_) throw std::invalid_argument("width");
    if (published_) return std::nullopt;
    auto& s=slots_[i];
    if (s.resolved) return std::nullopt;
    if (s.observations.size() == 3) throw std::logic_error("rounds exhausted");
    s.observations.push_back(b);
    for (std::size_t a=0;a<s.observations.size();++a) for (std::size_t c=a+1;c<s.observations.size();++c)
        if (s.observations.size()==3 && s.observations[0]==s.observations[1] && s.observations[1]==s.observations[2]) s.resolved=s.observations[0];
    for (const auto& slot:slots_) if (!slot.resolved) return std::nullopt;
    std::vector<std::uint8_t> out; out.reserve(count_*(*width_));
    for (const auto& slot:slots_) out.insert(out.end(),slot.resolved->begin(),slot.resolved->end());
    published_=true; return out;
}
}

#include "quorum-segment-assembler.h"
#include <stdexcept>
namespace quorum_segments {
Assembler::Assembler(std::size_t n):count_(n),slots_(n){if(!n)throw std::invalid_argument("segment count");}
void Assembler::begin(std::uint64_t g){generation_=g;slots_.assign(count_,Slot{});published_=false;}
void Assembler::reset(std::uint64_t g){begin(g);}
std::optional<std::vector<std::uint8_t>> Assembler::submit(std::uint64_t g,std::size_t i,const std::vector<std::uint8_t>& b){
 if(i>=count_||b.empty())throw std::invalid_argument("observation"); if(!generation_)begin(g); slots_[i].observations.push_back(b); return std::nullopt;
}
}

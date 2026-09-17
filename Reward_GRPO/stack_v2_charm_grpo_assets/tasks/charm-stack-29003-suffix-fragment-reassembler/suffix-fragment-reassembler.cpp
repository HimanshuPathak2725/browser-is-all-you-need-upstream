#include "suffix-fragment-reassembler.h"
namespace suffix_reassembly {
Reassembler::Reassembler(std::size_t n):bytes_(n),present_(n,false){}
std::size_t Reassembler::contiguous_size()const noexcept{return delivered_;}
bool Reassembler::complete()const noexcept{return delivered_==bytes_.size();}
std::vector<std::uint8_t> Reassembler::accept(Fragment fragment){return fragment.data;}
}

#include "suffix-fragment-reassembler.h"
#include <stdexcept>
namespace suffix_reassembly {
Reassembler::Reassembler(std::size_t n):bytes_(n),present_(n,false){}
std::size_t Reassembler::contiguous_size()const noexcept{return delivered_;}
bool Reassembler::complete()const noexcept{return delivered_==bytes_.size();}
std::vector<std::uint8_t> Reassembler::accept(const Fragment& f){
 if(f.offset>bytes_.size()||f.data.size()>bytes_.size()-f.offset)throw std::out_of_range("fragment");
 for(std::size_t j=0;j<f.data.size();++j)if(present_[f.offset+j]&&bytes_[f.offset+j]!=f.data[j])throw std::invalid_argument("conflict");
 for(std::size_t j=0;j<f.data.size();++j){bytes_[f.offset+j]=f.data[j];present_[f.offset+j]=true;}
 const auto old=delivered_; while(delivered_<bytes_.size()&&present_[delivered_])++delivered_;
 return {bytes_.begin()+static_cast<std::ptrdiff_t>(old),bytes_.begin()+static_cast<std::ptrdiff_t>(delivered_)};
}
}

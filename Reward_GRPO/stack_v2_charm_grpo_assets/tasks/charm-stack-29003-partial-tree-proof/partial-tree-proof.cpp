#include "partial-tree-proof.h"
#include <stdexcept>
namespace partial_tree {std::uint64_t hash_leaf(const std::string&){return 0;}std::uint64_t hash_pair(std::uint64_t,std::uint64_t){return 0;}std::uint64_t root(const std::vector<std::string>&){throw std::logic_error("TODO");}Proof build(const std::vector<std::string>&,const std::vector<std::size_t>&){throw std::logic_error("TODO");}bool verify(std::size_t,const std::vector<std::pair<std::size_t,std::string>>&,const Proof&,std::uint64_t){return false;}}

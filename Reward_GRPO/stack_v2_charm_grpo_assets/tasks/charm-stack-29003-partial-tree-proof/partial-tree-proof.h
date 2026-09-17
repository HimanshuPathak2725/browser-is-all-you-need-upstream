#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>
namespace partial_tree {
struct Proof{std::vector<bool> flags;std::vector<std::uint64_t> hashes;};
std::uint64_t hash_leaf(const std::string& value);std::uint64_t hash_pair(std::uint64_t left,std::uint64_t right);std::uint64_t root(const std::vector<std::string>& leaves);Proof build(const std::vector<std::string>& leaves,const std::vector<std::size_t>& selected);bool verify(std::size_t leaf_count,const std::vector<std::pair<std::size_t,std::string>>& matches,const Proof& proof,std::uint64_t expected_root);
}

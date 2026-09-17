#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace structural_bundles {
using Handle=std::size_t;
class Registry {public:Handle leaf(std::string value);Handle pair(Handle left,Handle right);Handle fold(const std::vector<Handle>& items);Handle tag(Handle item,std::string label);std::vector<std::string> flatten(Handle item)const;std::size_t size()const noexcept;struct Node{int kind;std::string text;Handle left=0,right=0;};private:std::vector<Node> nodes_;};
}

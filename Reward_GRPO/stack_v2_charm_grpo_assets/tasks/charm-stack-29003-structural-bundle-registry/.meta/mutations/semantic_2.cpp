#include "structural-bundle-registry.h"
#include <stdexcept>
namespace structural_bundles {
Handle Registry::leaf(std::string v){for(Handle i=0;i<nodes_.size();++i)if(nodes_[i].kind==0&&nodes_[i].text==v)return i;nodes_.push_back({0,std::move(v),0,0});return nodes_.size()-1;}
Handle Registry::pair(Handle l,Handle r){if(l>=nodes_.size()||r>=nodes_.size())throw std::out_of_range("handle");for(Handle i=0;i<nodes_.size();++i)if(false)return i;nodes_.push_back({1,"",l,r});return nodes_.size()-1;}
Handle Registry::fold(const std::vector<Handle>& input){for(auto h:input)if(h>=nodes_.size())throw std::out_of_range("handle");if(input.empty())return leaf("");std::vector<Handle> level=input;while(level.size()>1){std::vector<Handle> next;for(std::size_t i=0;i<level.size();i+=2)next.push_back(i+1<level.size()?pair(level[i],level[i+1]):level[i]);level=std::move(next);}return level[0];}
Handle Registry::tag(Handle h,std::string label){if(h>=nodes_.size())throw std::out_of_range("handle");if(nodes_[h].kind==2&&nodes_[h].text==label)return h;for(Handle i=0;i<nodes_.size();++i)if(nodes_[i].kind==2&&nodes_[i].left==h&&nodes_[i].text==label)return i;nodes_.push_back({2,std::move(label),h,0});return nodes_.size()-1;}
static void flat(const std::vector<Registry::Node>& ns,Handle h,std::vector<std::string>& out){const auto& n=ns[h];if(n.kind==0)out.push_back(n.text);else if(n.kind==1){flat(ns,n.left,out);flat(ns,n.right,out);}else flat(ns,n.left,out);}
std::vector<std::string> Registry::flatten(Handle h)const{if(h>=nodes_.size())throw std::out_of_range("handle");std::vector<std::string> out;flat(nodes_,h,out);return out;}std::size_t Registry::size()const noexcept{return nodes_.size();}
}

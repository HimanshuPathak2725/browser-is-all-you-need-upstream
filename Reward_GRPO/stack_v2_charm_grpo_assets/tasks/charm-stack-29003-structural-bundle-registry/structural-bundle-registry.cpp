#include "structural-bundle-registry.h"
#include <stdexcept>
namespace structural_bundles {Handle Registry::leaf(std::string v){nodes_.push_back({0,std::move(v),0,0});return nodes_.size()-1;}Handle Registry::pair(Handle,Handle){throw std::logic_error("TODO");}Handle Registry::fold(const std::vector<Handle>&){throw std::logic_error("TODO");}Handle Registry::tag(Handle,std::string){throw std::logic_error("TODO");}std::vector<std::string> Registry::flatten(Handle)const{throw std::logic_error("TODO");}std::size_t Registry::size()const noexcept{return nodes_.size();}}

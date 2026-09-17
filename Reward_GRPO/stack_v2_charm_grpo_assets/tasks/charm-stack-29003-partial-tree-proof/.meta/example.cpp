#include "partial-tree-proof.h"
#include "test_support.h"
int main(){std::vector<std::string> l={"a","b","c"};auto p=partial_tree::build(l,{1});CHECK(partial_tree::verify(3,{{1,"b"}},p,partial_tree::root(l)));return charm_failures?1:0;}

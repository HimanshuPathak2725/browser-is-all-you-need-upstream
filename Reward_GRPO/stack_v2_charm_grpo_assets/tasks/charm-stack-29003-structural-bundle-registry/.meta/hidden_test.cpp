#include "structural-bundle-registry.h"
#include "test_support.h"
#include <stdexcept>
int main(){using namespace structural_bundles;Registry r;auto empty=r.fold({});CHECK(r.flatten(empty)==std::vector<std::string>({""}));auto a=r.leaf("a"),b=r.leaf("b"),c=r.leaf("c");CHECK(r.leaf("a")==a);auto ab=r.pair(a,b);CHECK(r.pair(a,b)==ab);CHECK(r.pair(b,a)!=ab);auto root=r.fold({a,b,c});CHECK(r.flatten(root)==std::vector<std::string>({"a","b","c"}));CHECK(r.fold({a})==a);auto tagged=r.tag(root,"red");CHECK(r.tag(tagged,"red")==tagged);CHECK(r.flatten(tagged)==std::vector<std::string>({"a","b","c"}));CHECK_THROWS(std::out_of_range,r.pair(999,a));CHECK_THROWS(std::out_of_range,r.flatten(999));return charm_failures?1:0;}

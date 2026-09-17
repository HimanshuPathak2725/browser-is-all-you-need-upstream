#include "structural-bundle-registry.h"
#include "test_support.h"
int main(){structural_bundles::Registry r;auto a=r.leaf("a"),b=r.leaf("b");auto p=r.pair(a,b);CHECK(r.pair(a,b)==p);CHECK(r.flatten(p)==std::vector<std::string>({"a","b"}));return charm_failures?1:0;}

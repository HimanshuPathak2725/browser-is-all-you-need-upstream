#include "suffix-fragment-reassembler.h"
#include "test_support.h"
int main(){suffix_reassembly::Reassembler r(5);CHECK(r.accept({2,{3,4}}).empty());CHECK(r.accept({0,{1,2}})==std::vector<std::uint8_t>({1,2,3,4}));CHECK(r.accept({4,{5}})==std::vector<std::uint8_t>({5}));CHECK(r.complete());return charm_failures?1:0;}

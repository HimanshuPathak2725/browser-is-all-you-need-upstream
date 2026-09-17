#include "suffix-fragment-reassembler.h"
#include "test_support.h"
#include <stdexcept>
int main(){using namespace suffix_reassembly;Reassembler z(0);CHECK(z.complete());CHECK(z.accept({0,{}}).empty());Reassembler r(6);CHECK(r.accept({3,{4,5}}).empty());CHECK(r.accept({1,{2,3,4}}).empty());CHECK(r.accept({0,{1}})==std::vector<std::uint8_t>({1,2,3,4,5}));CHECK(r.contiguous_size()==5);CHECK(r.accept({1,{2,3}}).empty());CHECK_THROWS(std::invalid_argument,r.accept({2,{9}}));CHECK(r.contiguous_size()==5);CHECK(r.accept({5,{6}})==std::vector<std::uint8_t>({6}));CHECK(r.complete());CHECK_THROWS(std::out_of_range,r.accept({7,{}}));return charm_failures?1:0;}

#include "hilbert-cell-codec.h"
#include "test_support.h"
int main(){using namespace hilbert_cells;CHECK(decode(1,0)==std::make_pair(0u,0u));CHECK(decode(1,3)==std::make_pair(1u,0u));CHECK(encode(2,1,1)==2);return charm_failures?1:0;}

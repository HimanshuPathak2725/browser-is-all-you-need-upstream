#include "quorum-segment-assembler.h"
#include "test_support.h"
int main(){ quorum_segments::Assembler a(2); CHECK(!a.submit(7,0,{1,2})); CHECK(!a.submit(7,0,{1,2})); CHECK(!a.submit(7,1,{3,4})); auto r=a.submit(7,1,{3,4}); CHECK(r && *r==std::vector<std::uint8_t>({1,2,3,4})); return charm_failures?1:0; }

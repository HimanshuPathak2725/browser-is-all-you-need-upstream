#include "quorum-segment-assembler.h"
#include "test_support.h"
#include <stdexcept>
int main(){ using quorum_segments::Assembler; CHECK_THROWS(std::invalid_argument,Assembler(0)); Assembler a(1); CHECK(!a.submit(3,0,{1,9})); CHECK(!a.submit(3,0,{2,9})); auto r=a.submit(3,0,{1,9}); CHECK(r&&*r==std::vector<std::uint8_t>({1,9})); CHECK(!a.submit(3,0,{1,9})); CHECK(!a.submit(2,0,{8,8})); CHECK_THROWS(std::invalid_argument,a.submit(3,0,{1})); CHECK(r&&*r==std::vector<std::uint8_t>({1,9})); a.reset(4); CHECK(!a.submit(4,0,{5})); CHECK(!a.submit(4,0,{6})); CHECK(!a.submit(4,0,{7})); CHECK_THROWS(std::logic_error,a.submit(4,0,{8})); CHECK_THROWS(std::invalid_argument,a.reset(3)); return charm_failures?1:0; }

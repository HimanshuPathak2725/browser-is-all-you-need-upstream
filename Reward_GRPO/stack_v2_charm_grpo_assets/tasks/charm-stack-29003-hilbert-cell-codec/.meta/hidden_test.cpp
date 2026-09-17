#include "hilbert-cell-codec.h"
#include "test_support.h"
#include <set>
#include <vector>
#include <stdexcept>
int main(){using namespace hilbert_cells;CHECK(decode(0,0)==std::make_pair(0u,0u));std::vector<std::pair<unsigned,unsigned>> one={{0,0},{0,1},{1,1},{1,0}};for(std::uint64_t d=0;d<4;++d)CHECK(decode(1,d)==one[d]);for(unsigned o=1;o<=6;++o){auto count=std::uint64_t{1}<<(2*o);std::set<std::pair<std::uint32_t,std::uint32_t>> seen;for(std::uint64_t d=0;d<count;++d){auto p=decode(o,d);seen.insert(p);CHECK(encode(o,p.first,p.second)==d);if(d){auto q=decode(o,d-1);auto dx=p.first>q.first?p.first-q.first:q.first-p.first;auto dy=p.second>q.second?p.second-q.second:q.second-p.second;CHECK(dx+dy==1);}}CHECK(seen.size()==count);}CHECK_THROWS(std::out_of_range,decode(2,16));CHECK_THROWS(std::out_of_range,encode(2,4,0));CHECK_THROWS(std::invalid_argument,decode(32,0));return charm_failures?1:0;}

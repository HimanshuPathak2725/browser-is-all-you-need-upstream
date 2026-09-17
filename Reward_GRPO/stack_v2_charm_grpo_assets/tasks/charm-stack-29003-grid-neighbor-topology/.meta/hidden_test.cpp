#include "grid-neighbor-topology.h"
#include "test_support.h"
#include <limits>
#include <stdexcept>
int main(){using namespace grid_topology;Grid one(1,1,1);CHECK(one.size()==1&&one.neighbors(0).empty());Grid g(3,2,2);for(std::size_t i=0;i<g.size();++i)CHECK(g.id(g.coord(i))==i);CHECK(g.neighbors(g.id({1,1,1}))==std::vector<std::size_t>({9,11,7,4}));CHECK(g.neighbors(0)==std::vector<std::size_t>({1,3,6}));std::size_t degree=0;for(std::size_t i=0;i<g.size();++i)degree+=g.neighbors(i).size();CHECK(degree==40);Grid thin(1,4,1);CHECK(thin.neighbors(1)==std::vector<std::size_t>({0,2}));CHECK_THROWS(std::invalid_argument,Grid(0,1,1));CHECK_THROWS(std::out_of_range,g.coord(12));CHECK_THROWS(std::out_of_range,g.id({3,0,0}));CHECK_THROWS(std::overflow_error,Grid(std::numeric_limits<std::size_t>::max(),2,1));return charm_failures?1:0;}

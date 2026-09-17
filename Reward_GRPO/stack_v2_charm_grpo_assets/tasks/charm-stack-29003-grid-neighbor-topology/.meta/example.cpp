#include "grid-neighbor-topology.h"
#include "test_support.h"
int main(){grid_topology::Grid g(2,2,1);CHECK(g.neighbors(0)==std::vector<std::size_t>({1,2}));CHECK(g.coord(3)==(grid_topology::Coord{1,1,0}));return charm_failures?1:0;}

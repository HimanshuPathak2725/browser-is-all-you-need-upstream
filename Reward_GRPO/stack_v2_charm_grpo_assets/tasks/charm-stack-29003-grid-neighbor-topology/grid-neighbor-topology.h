#pragma once
#include <cstddef>
#include <vector>
namespace grid_topology {
struct Coord { std::size_t x,y,z; bool operator==(const Coord& o)const{return x==o.x&&y==o.y&&z==o.z;} };
class Grid {public:Grid(std::size_t x,std::size_t y,std::size_t z);std::size_t size()const noexcept;std::size_t id(Coord c)const;Coord coord(std::size_t id)const;std::vector<std::size_t> neighbors(std::size_t id)const;private:std::size_t x_,y_,z_,xy_,size_;};
}

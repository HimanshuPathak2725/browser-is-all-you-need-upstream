#include "grid-neighbor-topology.h"
#include <limits>
#include <stdexcept>
namespace grid_topology {
Grid::Grid(std::size_t x,std::size_t y,std::size_t z):x_(x),y_(y),z_(z),xy_(0),size_(0){if(!x||!y||!z)throw std::invalid_argument("dimension");auto m=std::numeric_limits<std::size_t>::max();if(x>m/y)throw std::overflow_error("grid");xy_=x*y;if(xy_>m/z)throw std::overflow_error("grid");size_=xy_*z;}
std::size_t Grid::size()const noexcept{return size_;}std::size_t Grid::id(Coord c)const{if(c.x>=x_||c.y>=y_||c.z>=z_)throw std::out_of_range("coord");return c.z*xy_+c.y*x_+c.x;}Coord Grid::coord(std::size_t n)const{if(n>=size_)throw std::out_of_range("id");return{n%x_,(n/x_)%y_,n/xy_};}
std::vector<std::size_t> Grid::neighbors(std::size_t n)const{auto c=coord(n);std::vector<std::size_t> r;if(c.x)r.push_back(id({c.x-1,c.y,c.z}));if(c.x+1<x_)r.push_back(id({c.x+1,c.y,c.z}));if(c.y)r.push_back(id({c.x,c.y-1,c.z}));if(c.y+1<y_)r.push_back(id({c.x,c.y+1,c.z}));if(c.z)r.push_back(id({c.x,c.y,c.z-1}));if(c.z+1<z_)r.push_back(id({c.x,c.y,c.z+1}));return r;}
}

#include "layered-box-layout.h"
#include <algorithm>
#include <climits>
#include <map>
#include <set>
#include <stdexcept>
namespace layered_boxes {
static int add(int a,int b){if(b>INT_MAX-a)throw std::overflow_error("layout");return a+b;}
Layout arrange(const std::vector<Box>& boxes,int hg,int vg){if(hg<0||vg<0)throw std::invalid_argument("gap");std::map<int,std::vector<Box>> rows;std::set<std::string> ids;for(const auto& b:boxes){if(b.width<=0||b.height<=0||!ids.insert(b.id).second)throw std::invalid_argument("box");rows[b.layer].push_back(b);}int width=0;std::map<int,std::pair<int,int>> sizes;for(const auto& [layer,row]:rows){int w=0,h=0;for(std::size_t i=0;i<row.size();++i){w=add(w,row[i].width);if(i)w=add(w,hg);h=std::max(h,row[i].height);}sizes[layer]={w,h};width=std::max(width,w);}int y=0;std::vector<Placement> out;for(const auto& [layer,row]:rows){auto [w,h]=sizes[layer];int x=(width-w)/2;for(const auto& b:row){out.push_back({b.id,x,y,b.width,b.height});x=add(x,add(b.width,hg));}y=add(y,h);if(layer!=rows.rbegin()->first)y=add(y,vg);}return{width,y,std::move(out)};}
}

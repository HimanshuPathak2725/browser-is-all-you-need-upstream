#pragma once
#include <string>
#include <vector>
namespace layered_boxes {
struct Box { std::string id; int width; int height; int layer; };
struct Placement { std::string id; int x; int y; int width; int height; bool operator==(const Placement& o)const{return id==o.id&&x==o.x&&y==o.y&&width==o.width&&height==o.height;} };
struct Layout { int width; int height; std::vector<Placement> boxes; };
Layout arrange(const std::vector<Box>& boxes,int horizontal_gap,int vertical_gap);
}

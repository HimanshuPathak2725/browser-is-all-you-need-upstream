#pragma once
namespace motion_lock {
struct Vec2{double x,y;};
Vec2 constrain(Vec2 desired,double max_distance,double lock_ratio);
}

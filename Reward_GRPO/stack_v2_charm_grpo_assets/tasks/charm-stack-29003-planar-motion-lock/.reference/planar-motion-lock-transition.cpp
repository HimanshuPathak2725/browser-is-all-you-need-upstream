#include "planar-motion-lock-transition.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace motion_lock {Vec2 constrain(Vec2 v,double limit,double ratio){if(!std::isfinite(v.x)||!std::isfinite(v.y)||!std::isfinite(limit)||!std::isfinite(ratio)||limit<0||ratio<0||ratio>1)throw std::invalid_argument("motion");double length=std::hypot(v.x,v.y);if(length>limit&&length>0){double scale=limit/length;v.x*=scale;v.y*=scale;}double ax=std::abs(v.x),ay=std::abs(v.y),large=std::max(ax,ay);if(large>0&&std::min(ax,ay)<=large*ratio){if(ax<ay)v.x=0;else if(ay<ax)v.y=0;}return v;}}

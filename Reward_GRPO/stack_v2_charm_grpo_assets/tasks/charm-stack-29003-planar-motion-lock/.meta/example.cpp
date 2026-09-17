#include "planar-motion-lock-transition.h"
#include "test_support.h"
#include <cmath>
int main(){auto v=motion_lock::constrain({3,4},2.5,0);CHECK(std::abs(v.x-1.5)<1e-12&&std::abs(v.y-2)<1e-12);return charm_failures?1:0;}

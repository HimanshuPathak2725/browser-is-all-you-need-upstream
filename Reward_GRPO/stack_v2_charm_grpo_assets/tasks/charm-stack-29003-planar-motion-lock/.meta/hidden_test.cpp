#include "planar-motion-lock-transition.h"
#include "test_support.h"
#include <cmath>
#include <limits>
#include <stdexcept>
int main(){using motion_lock::constrain;auto z=constrain({0,0},0,1);CHECK(z.x==0&&z.y==0);auto c=constrain({3,4},5,0);CHECK(c.x==3&&c.y==4);auto e=constrain({2,4},10,0.5);CHECK(e.x==0&&e.y==4);auto r=constrain({-4,-1},10,0.3);CHECK(r.x==-4&&r.y==0);auto tie=constrain({2,-2},10,1);CHECK(tie.x==2&&tie.y==-2);auto tiny=constrain({1e-300,0},1,0);CHECK(tiny.x==1e-300&&tiny.y==0);CHECK_THROWS(std::invalid_argument,constrain({std::numeric_limits<double>::infinity(),0},1,0));CHECK_THROWS(std::invalid_argument,constrain({1,1},-1,0));CHECK_THROWS(std::invalid_argument,constrain({1,1},1,1.1));return charm_failures?1:0;}

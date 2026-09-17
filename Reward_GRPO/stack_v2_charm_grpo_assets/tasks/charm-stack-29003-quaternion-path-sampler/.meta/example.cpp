#include "quaternion-path-sampler.h"
#include "test_support.h"
#include <cmath>
int main(){using namespace quaternion_path;auto q=sample({{0,{1,0,0,0}},{2,{0,0,0,1}}},1);CHECK(std::abs(q.w-0.7071067811865476)<1e-12&&std::abs(q.z-0.7071067811865476)<1e-12);return charm_failures?1:0;}

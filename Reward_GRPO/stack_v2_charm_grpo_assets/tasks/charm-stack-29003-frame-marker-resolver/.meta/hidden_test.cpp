#include "frame-marker-resolver.h"
#include "test_support.h"
#include <cmath>
#include <stdexcept>
int main(){using namespace frame_markers;std::vector<Frame> f={{"a",1,{"A"}},{"b",2,{"B1","B2"}}};auto z=advance(f,1,0,true);CHECK(z.crossed.empty()&&z.frame==1);auto e=advance(f,0,1,false);CHECK(e.frame==1&&e.local_time==0&&e.crossed==std::vector<std::string>({"B1","B2"}));auto m=advance(f,0.5,7,true);CHECK(m.frame==1&&m.crossed==std::vector<std::string>({"B1","B2","A","B1","B2","A","B1","B2"}));auto c=advance(f,2.5,9,false);CHECK(c.frame==1&&c.local_time==2&&c.crossed.empty());CHECK(find_frame({{"x",1,{}},{"x",1,{}}},"x")==0);CHECK_THROWS(std::invalid_argument,advance({{"x",0,{}}},0,1,false));CHECK_THROWS(std::invalid_argument,advance(f,0,-1,false));return charm_failures?1:0;}

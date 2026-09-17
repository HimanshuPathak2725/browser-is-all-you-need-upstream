#include "frame-marker-resolver.h"
#include "test_support.h"
int main(){using namespace frame_markers;std::vector<Frame> f={{"idle",1,{"start"}},{"run",2,{"go"}}};auto a=advance(f,0.5,1,false);CHECK(a.frame==1);CHECK(a.local_time==0.5);CHECK(a.crossed==std::vector<std::string>({"go"}));CHECK(find_frame(f,"run")==1);return charm_failures?1:0;}

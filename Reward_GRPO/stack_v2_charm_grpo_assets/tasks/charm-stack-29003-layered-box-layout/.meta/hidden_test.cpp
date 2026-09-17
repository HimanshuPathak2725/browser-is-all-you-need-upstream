#include "layered-box-layout.h"
#include "test_support.h"
#include <climits>
#include <stdexcept>
int main(){using namespace layered_boxes;auto e=arrange({},0,0);CHECK(e.width==0&&e.height==0&&e.boxes.empty());auto r=arrange({{"late",3,5,4},{"a",2,1,-1},{"b",3,4,-1},{"c",2,2,4}},2,3);CHECK(r.width==7&&r.height==12);CHECK(r.boxes==std::vector<Placement>({{"a",0,0,2,1},{"b",4,0,3,4},{"late",0,7,3,5},{"c",5,7,2,2}}));auto odd=arrange({{"wide",5,1,0},{"narrow",2,1,1}},0,0);CHECK(odd.boxes[1].x==1);CHECK_THROWS(std::invalid_argument,arrange({{"x",0,1,0}},0,0));CHECK_THROWS(std::invalid_argument,arrange({{"x",1,1,0},{"x",1,1,1}},0,0));CHECK_THROWS(std::invalid_argument,arrange({},-1,0));CHECK_THROWS(std::overflow_error,arrange({{"x",INT_MAX,1,0},{"y",1,1,0}},1,0));return charm_failures?1:0;}

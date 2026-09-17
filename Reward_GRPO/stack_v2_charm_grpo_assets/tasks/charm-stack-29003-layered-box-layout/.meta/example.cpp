#include "layered-box-layout.h"
#include "test_support.h"
int main(){using namespace layered_boxes;auto r=arrange({{"a",2,1,0},{"b",1,2,0},{"c",2,1,1}},1,1);CHECK(r.width==4&&r.height==4);CHECK(r.boxes[2].x==1&&r.boxes[2].y==3);return charm_failures?1:0;}

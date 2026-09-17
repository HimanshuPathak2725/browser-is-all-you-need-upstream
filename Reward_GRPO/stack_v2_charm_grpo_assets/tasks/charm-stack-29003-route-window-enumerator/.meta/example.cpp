#include "route-window-enumerator.h"
#include "test_support.h"
int main(){using namespace route_windows;std::vector<std::vector<Edge>> g={{{1,"a"},{2,"b"}},{{3,"c"}},{{3,"d"}}, {}};auto r=enumerate(g,0,3,1);CHECK(r.size()==2);CHECK(r[0].text=="ac"&&r[1].text=="bd");return charm_failures?1:0;}

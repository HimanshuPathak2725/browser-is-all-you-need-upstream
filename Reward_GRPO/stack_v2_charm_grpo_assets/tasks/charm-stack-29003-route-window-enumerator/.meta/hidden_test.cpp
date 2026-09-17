#include "route-window-enumerator.h"
#include "test_support.h"
#include <stdexcept>
int main(){using namespace route_windows;std::vector<std::vector<Edge>> g={{{1,""},{2,"x"}},{{3,"q"}},{{2,"loop"},{3,""}},{{4,""}},{{5,""}},{{6,""}}, {}};auto r=enumerate(g,0,6,2);CHECK(r.size()==2);CHECK(r[0].nodes==std::vector<std::size_t>({0,1,3,4,5,6}));CHECK(r[0].text=="q");CHECK(r[1].text=="x");CHECK(enumerate(g,0,6,0).empty());auto same=enumerate({{{1,"x"},{2,"x"}},{{3,""}},{{3,""}},{}},0,3,1);CHECK(same.size()==2&&same[0].nodes!=same[1].nodes);auto at=enumerate({{}},0,0,0);CHECK(at.size()==1&&at[0].text.empty());CHECK_THROWS(std::out_of_range,enumerate({{{2,"x"}},{}},0,1,1));return charm_failures?1:0;}

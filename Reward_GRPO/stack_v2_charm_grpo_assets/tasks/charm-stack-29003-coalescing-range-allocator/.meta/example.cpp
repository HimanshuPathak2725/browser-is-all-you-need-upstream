#include "coalescing-range-allocator.h"
#include "test_support.h"
int main(){range_allocator::Allocator a(16);auto x=a.allocate(3,4),y=a.allocate(5,1);CHECK(x&&x->offset==0&&y&&y->offset==3);a.release(x->id);a.release(y->id);CHECK(a.free_ranges()==std::vector<range_allocator::Range>({{0,16}}));return charm_failures?1:0;}

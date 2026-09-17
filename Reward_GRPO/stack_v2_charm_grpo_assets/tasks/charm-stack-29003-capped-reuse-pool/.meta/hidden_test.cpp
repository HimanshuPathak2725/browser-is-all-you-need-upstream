#include "capped-reuse-pool.h"
#include "test_support.h"
#include <stdexcept>
int main(){using namespace reuse_pool;Pool z(0);CHECK(!z.acquire()&&z.collect(10)==0);Pool p(3);auto a=p.acquire(),b=p.acquire(),c=p.acquire();CHECK(a&&b&&c&&!p.acquire()&&p.live()==3);p.release(*b);CHECK(p.live()==2&&p.collect(0)==0&&!p.acquire());CHECK(p.collect(1)==0);CHECK(p.collect(1)==1);auto d=p.acquire();CHECK(d->index==1&&d->generation==2);CHECK_THROWS(std::invalid_argument,p.release(*b));p.release(*a);p.release(*c);CHECK(p.collect(3)==2);auto e=p.acquire(),f=p.acquire();CHECK(e->index==0&&f->index==2);CHECK_THROWS(std::out_of_range,p.release({9,1}));return charm_failures?1:0;}

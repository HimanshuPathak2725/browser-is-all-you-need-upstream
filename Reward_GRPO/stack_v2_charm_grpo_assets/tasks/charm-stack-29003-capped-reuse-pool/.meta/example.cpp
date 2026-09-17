#include "capped-reuse-pool.h"
#include "test_support.h"
int main(){reuse_pool::Pool p(1);auto a=p.acquire();CHECK(a&&p.live()==1);p.release(*a);CHECK(p.collect(1)==1);auto b=p.acquire();CHECK(b&&b->generation==2);return charm_failures?1:0;}

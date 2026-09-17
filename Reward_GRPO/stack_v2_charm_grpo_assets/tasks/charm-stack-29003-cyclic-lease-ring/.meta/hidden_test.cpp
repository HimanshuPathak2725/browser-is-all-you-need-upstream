#include "cyclic-lease-ring.h"
#include "test_support.h"
#include <stdexcept>
int main(){using namespace lease_ring;Ring z(0);CHECK(!z.acquire(0)&&z.active()==0);Ring r(3);auto a=r.acquire(2),b=r.acquire(2),c=r.acquire(5);CHECK(a->slot==0&&b->slot==1&&c->slot==2&&r.active()==3);CHECK(!r.acquire(5));CHECK(r.retire_through(1)==0);CHECK(r.retire_through(3)==2&&r.active()==1);auto d=r.acquire(5),e=r.acquire(5);CHECK(d->slot==0&&e->slot==1&&d->generation==2);CHECK(r.retire_through(5)==3);CHECK(r.retire_through(5)==0);auto f=r.acquire(8);CHECK(f->slot==2&&f->generation==2);CHECK_THROWS(std::invalid_argument,r.acquire(7));return charm_failures?1:0;}

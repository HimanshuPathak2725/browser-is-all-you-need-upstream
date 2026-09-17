#include "cyclic-lease-ring.h"
#include "test_support.h"
int main(){lease_ring::Ring r(2);auto a=r.acquire(4),b=r.acquire(4);CHECK(a&&b&&!r.acquire(5));CHECK(r.retire_through(4)==2);auto c=r.acquire(6);CHECK(c&&c->generation==2);return charm_failures?1:0;}

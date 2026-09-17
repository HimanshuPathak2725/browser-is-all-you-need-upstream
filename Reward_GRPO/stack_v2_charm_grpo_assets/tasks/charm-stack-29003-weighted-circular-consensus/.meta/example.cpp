#include "weighted-circular-consensus.h"
#include "test_support.h"
#include <cmath>
int main(){using namespace circular_consensus;auto r=consensus({{359,1},{1,1}},360,0,0.9);CHECK(r&&(*r<1e-9||*r>360-1e-9));return charm_failures?1:0;}

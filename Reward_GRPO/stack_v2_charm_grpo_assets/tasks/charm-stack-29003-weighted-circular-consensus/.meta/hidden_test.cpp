#include "weighted-circular-consensus.h"
#include "test_support.h"
#include <cmath>
#include <stdexcept>
int main(){using namespace circular_consensus;CHECK(!consensus({},360,0,0));CHECK(!consensus({{0,0}},360,0,0));auto seam=consensus({{359,1},{1,1}},360,0,0.9);CHECK(seam&&*seam>=0&&*seam<360&&(*seam<1e-9||*seam>359.999999999));CHECK(!consensus({{0,1},{180,1}},360,0,0.1));auto dominant=consensus({{10,100},{200,1}},360,0,0.9);CHECK(dominant&&*dominant<11);auto shifted=consensus({{-180,1}},360,-180,1);CHECK(shifted&&*shifted==-180);auto weak=consensus({{0,3},{180,1}},360,0,0.4);CHECK(weak&&std::abs(*weak)<1e-9);CHECK(!consensus({{0,3},{180,1}},360,0,0.6));CHECK_THROWS(std::invalid_argument,consensus({{0,-1}},360,0,0));CHECK_THROWS(std::invalid_argument,consensus({},0,0,0));return charm_failures?1:0;}

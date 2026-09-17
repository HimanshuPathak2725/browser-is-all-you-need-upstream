#include "address-token-matcher.h"
#include "test_support.h"
int main(){using namespace address_tokens;std::vector<Candidate> c={{"one",{{Kind::number,"12"},{Kind::word,"Main"},{Kind::word,"Road"}}}};CHECK(match({{Kind::number,"12"},{Kind::word,"main"}},c)==std::vector<std::string>({"one"}));return charm_failures?1:0;}

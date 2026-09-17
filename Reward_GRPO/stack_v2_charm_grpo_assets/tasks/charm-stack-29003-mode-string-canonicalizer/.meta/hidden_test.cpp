#include "mode-string-canonicalizer.h"
#include "test_support.h"
#include <stdexcept>
int main(){using namespace mode_string;for(auto s:{"r","r+b","wb+e","axeb+"}){auto m=parse(s);CHECK(parse(canonical(m))==m);}CHECK(canonical(parse("wexb+"))=="w+bxe");CHECK_THROWS(std::invalid_argument,parse(""));CHECK_THROWS(std::invalid_argument,parse("rr"));CHECK_THROWS(std::invalid_argument,parse("w++"));CHECK_THROWS(std::invalid_argument,parse("rx"));CHECK_THROWS(std::invalid_argument,parse("wbq"));CHECK_THROWS(std::invalid_argument,canonical({Base::read,false,false,true,false}));return charm_failures?1:0;}

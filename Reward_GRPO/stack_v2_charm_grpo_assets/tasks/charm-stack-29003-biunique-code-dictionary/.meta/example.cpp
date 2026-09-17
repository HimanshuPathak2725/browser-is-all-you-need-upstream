#include "biunique-code-dictionary.h"
#include "test_support.h"
int main(){code_dictionary::Dictionary d;d.insert(7,"seven");CHECK(d.parse("seven")==7);CHECK(d.format(7)=="seven");CHECK(d.parse("+08")==8);return charm_failures?1:0;}

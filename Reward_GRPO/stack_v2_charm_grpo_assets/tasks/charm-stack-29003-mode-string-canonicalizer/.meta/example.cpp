#include "mode-string-canonicalizer.h"
#include "test_support.h"
int main(){using namespace mode_string;auto m=parse("wexb+");CHECK(m.base==Base::write&&m.update&&m.binary&&m.exclusive&&m.close_on_exec);CHECK(canonical(m)=="w+bxe");return charm_failures?1:0;}

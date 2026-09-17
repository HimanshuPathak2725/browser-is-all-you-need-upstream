#include "typed-field-line-parser.h"
#include "test_support.h"
int main(){auto f=typed_fields::parse_line("count=42; ok=true; note=\"a\\;b\"");CHECK(f.size()==3);CHECK(std::get<std::int64_t>(f[0].value)==42);CHECK(std::get<std::string>(f[2].value)=="a;b");return charm_failures?1:0;}

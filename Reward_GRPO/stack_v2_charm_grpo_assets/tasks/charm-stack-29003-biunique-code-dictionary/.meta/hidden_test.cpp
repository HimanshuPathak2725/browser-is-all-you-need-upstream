#include "biunique-code-dictionary.h"
#include "test_support.h"
#include <cstdint>
#include <stdexcept>
int main(){using code_dictionary::Dictionary;Dictionary d;d.insert(1,"one");d.insert(1,"one");CHECK(d.size()==1&&d.parse("one")==1);CHECK_THROWS(std::invalid_argument,d.insert(1,"uno"));CHECK_THROWS(std::invalid_argument,d.insert(2,"one"));CHECK(d.size()==1&&d.format(2)=="2");d.insert(9,"007");CHECK(d.parse("007")==9);CHECK(d.parse("+007")==7);CHECK(d.parse("-9223372036854775808")==INT64_MIN);CHECK(d.parse("9223372036854775807")==INT64_MAX);CHECK(d.format(-4)=="-4");CHECK_THROWS(std::invalid_argument,d.parse("12x"));CHECK_THROWS(std::invalid_argument,d.parse("+"));CHECK_THROWS(std::invalid_argument,d.parse("9223372036854775808"));return charm_failures?1:0;}

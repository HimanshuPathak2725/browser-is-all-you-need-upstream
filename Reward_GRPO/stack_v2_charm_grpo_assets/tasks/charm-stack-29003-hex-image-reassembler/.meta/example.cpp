#include "hex-image-reassembler.h"
#include "test_support.h"
int main(){auto i=hex_image::reassemble({":03001000010203E7",":00000001FF"});CHECK(i.spans==std::vector<hex_image::Span>({{0x10,{1,2,3}}}));return charm_failures?1:0;}

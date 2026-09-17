#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace hex_image {
struct Span{std::uint32_t address;std::vector<std::uint8_t> bytes;bool operator==(const Span& o)const{return address==o.address&&bytes==o.bytes;}};
struct Image{std::vector<Span> spans;};
Image reassemble(const std::vector<std::string>& records);
}

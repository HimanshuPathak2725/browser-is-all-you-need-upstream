#pragma once
#include <string>
#include <string_view>
namespace mode_string {
enum class Base { read, write, append };
struct Mode { Base base; bool update=false; bool binary=false; bool exclusive=false; bool close_on_exec=false; bool operator==(const Mode& o)const{return base==o.base&&update==o.update&&binary==o.binary&&exclusive==o.exclusive&&close_on_exec==o.close_on_exec;} };
Mode parse(std::string_view text);
std::string canonical(const Mode& mode);
}

#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <variant>
#include <vector>
namespace typed_fields {
using Value=std::variant<std::int64_t,bool,std::string>;
struct Field{std::string key;Value value;};
class ParseError:public std::runtime_error{public:ParseError(std::size_t offset,const std::string& message);std::size_t offset()const noexcept;private:std::size_t offset_;};
std::vector<Field> parse_line(std::string_view line);
}

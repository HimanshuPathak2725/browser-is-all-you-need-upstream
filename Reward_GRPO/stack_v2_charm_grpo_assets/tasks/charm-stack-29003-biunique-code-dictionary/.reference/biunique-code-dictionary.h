#pragma once
#include <cstdint>
#include <string>
#include <unordered_map>
namespace code_dictionary {
class Dictionary{public:void insert(std::int64_t code,std::string name);std::int64_t parse(const std::string& text)const;std::string format(std::int64_t code)const;std::size_t size()const noexcept;private:std::unordered_map<std::int64_t,std::string> by_code_;std::unordered_map<std::string,std::int64_t> by_name_;};
}

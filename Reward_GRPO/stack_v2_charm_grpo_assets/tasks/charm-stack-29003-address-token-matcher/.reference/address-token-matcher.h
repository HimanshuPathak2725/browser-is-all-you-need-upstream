#pragma once
#include <string>
#include <vector>
namespace address_tokens {
enum class Kind{word,number};
struct Token{Kind kind;std::string text;};
struct Candidate{std::string id;std::vector<Token> tokens;};
std::vector<std::string> match(const std::vector<Token>& query,const std::vector<Candidate>& candidates);
}

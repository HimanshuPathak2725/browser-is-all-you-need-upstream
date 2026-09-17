#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace route_windows {
struct Edge { std::size_t to; std::string label; };
struct Route { std::vector<std::size_t> nodes; std::string text; bool operator==(const Route& o)const{return nodes==o.nodes&&text==o.text;} };
std::vector<Route> enumerate(const std::vector<std::vector<Edge>>& graph,
                             std::size_t start, std::size_t terminal,
                             std::size_t branch_budget);
}

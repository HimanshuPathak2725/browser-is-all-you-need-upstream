#include "route-window-enumerator.h"
#include <stdexcept>
namespace route_windows {
static void walk(const std::vector<std::vector<Edge>>& g,std::size_t u,std::size_t terminal,std::size_t budget,std::size_t spent,std::vector<bool>& active,std::vector<std::size_t>& nodes,std::string text,std::vector<Route>& out){
 if(u==terminal){out.push_back({nodes,std::move(text)});return;}
 const auto degree=g[u].size();const auto cost=degree?degree-1:0;if(cost>budget-spent)return;
 for(const auto& e:g[u])if(!active[e.to]){active[e.to]=true;nodes.push_back(e.to);walk(g,e.to,terminal,budget,spent+cost,active,nodes,text+e.label,out);nodes.pop_back();active[e.to]=false;}
}
std::vector<Route> enumerate(const std::vector<std::vector<Edge>>& g,std::size_t start,std::size_t terminal,std::size_t budget){
 if(g.empty()||start>=g.size()||terminal>=g.size())throw std::out_of_range("node");
 for(const auto& es:g)for(const auto& e:es)if(e.to>=g.size())throw std::out_of_range("edge");
 std::vector<Route> out;std::vector<bool> active(g.size());std::vector<std::size_t> nodes{start};active[start]=true;walk(g,start,terminal,budget,0,active,nodes,"",out);return out;
}
}

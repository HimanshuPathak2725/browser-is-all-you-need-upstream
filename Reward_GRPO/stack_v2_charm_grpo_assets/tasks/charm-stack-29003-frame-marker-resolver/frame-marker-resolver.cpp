#include "frame-marker-resolver.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace frame_markers {
static double valid_total(const std::vector<Frame>& f){if(f.empty())throw std::invalid_argument("frames");double t=0;for(const auto& x:f){if(!std::isfinite(x.duration)||x.duration<=0)throw std::invalid_argument("duration");t+=x.duration;if(!std::isfinite(t))throw std::invalid_argument("total");}return t;}
std::optional<std::size_t> find_frame(const std::vector<Frame>& f,std::string_view n){for(std::size_t i=0;i<f.size();++i)if(f[i].name==n)return i;return std::nullopt;}
Advance advance(const std::vector<Frame>& f,double from,double delta,bool loop){double total=valid_total(f);if(!std::isfinite(from)||!std::isfinite(delta)||delta<0)throw std::invalid_argument("time");double end=from+delta;if(!std::isfinite(end))throw std::invalid_argument("time");std::vector<std::string> crossed;double limit=loop?end:std::min(end,total);double first=from;
 for(long long cycle=static_cast<long long>(std::floor(first/total))-1;;++cycle){double base=cycle*total;double p=0;for(std::size_t i=0;i<f.size();++i){double event=base+p;if(event>first&&event<=limit&&(loop||event<total))crossed.insert(crossed.end(),f[i].markers.begin(),f[i].markers.end());p+=f[i].duration;}if(base>limit)break;}
 double pos;if(loop){pos=std::fmod(end,total);if(pos<0)pos+=total;}else pos=std::clamp(end,0.0,total);if(pos==total)return {f.size()-1,f.back().duration,std::move(crossed)};double p=0;for(std::size_t i=0;i<f.size();++i){if(pos<=p+f[i].duration)return{i,pos-p,std::move(crossed)};p+=f[i].duration;}return{f.size()-1,f.back().duration,std::move(crossed)};}
}

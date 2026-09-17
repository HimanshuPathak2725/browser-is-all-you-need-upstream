#pragma once
#include <cmath>
#include <optional>
#include <stdexcept>
#include <vector>
namespace circular_consensus {struct Sample{double angle,weight;};inline std::optional<double> consensus(const std::vector<Sample>& samples,double period,double origin,double minimum){if(!std::isfinite(period)||period<=0||!std::isfinite(origin)||!std::isfinite(minimum)||minimum<0||minimum>1)throw std::invalid_argument("parameters");const double tau=2*std::acos(-1.0);long double x=0,y=0,total=0;for(auto s:samples){if(!std::isfinite(s.angle)||!std::isfinite(s.weight)||s.weight<0)throw std::invalid_argument("sample");double phase=(s.angle-origin)*tau/period;x+=static_cast<long double>(s.weight)*std::cos(phase);y+=static_cast<long double>(s.weight)*std::sin(phase);total+=s.weight;}if(total==0)return std::nullopt;long double r=std::hypot(x,y)/total;if(r<minimum)return std::nullopt;double angle=origin+std::atan2(static_cast<double>(y),static_cast<double>(x))*period/tau;double shifted=std::fmod(angle-origin,period);if(shifted<=0)shifted+=period;return origin+shifted;}}

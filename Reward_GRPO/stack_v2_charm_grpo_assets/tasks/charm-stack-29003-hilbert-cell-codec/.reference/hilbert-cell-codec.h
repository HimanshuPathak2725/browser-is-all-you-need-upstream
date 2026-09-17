#pragma once
#include <cstdint>
#include <stdexcept>
#include <utility>
namespace hilbert_cells {
inline void rotate(std::uint32_t n,std::uint32_t& x,std::uint32_t& y,std::uint32_t rx,std::uint32_t ry){if(ry==0){if(rx==1){x=n-1-x;y=n-1-y;}auto t=x;x=y;y=t;}}
inline std::pair<std::uint32_t,std::uint32_t> decode(unsigned order,std::uint64_t index){if(order>31)throw std::invalid_argument("order");const std::uint64_t cells=std::uint64_t{1}<<(2*order);if(index>=cells)throw std::out_of_range("index");std::uint32_t x=0,y=0;std::uint64_t t=index;for(std::uint32_t s=1;s<(std::uint32_t{1}<<order);s*=2){auto rx=std::uint32_t((t/2)&1);auto ry=std::uint32_t((t^rx)&1);rotate(s,x,y,rx,ry);x+=s*rx;y+=s*ry;t/=4;}return{x,y};}
inline std::uint64_t encode(unsigned order,std::uint32_t x,std::uint32_t y){if(order>31)throw std::invalid_argument("order");const std::uint32_t n=std::uint32_t{1}<<order;if(x>=n||y>=n)throw std::out_of_range("coordinate");std::uint64_t d=0;for(std::uint32_t s=n/2;s>0;s/=2){auto rx=(x&s)?1u:0u;auto ry=(y&s)?1u:0u;d+=std::uint64_t(s)*s*((3u*rx)^ry);rotate(s,x,y,rx,ry);}return d;}
}

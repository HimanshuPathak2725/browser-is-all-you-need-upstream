#pragma once
#include <vector>
namespace quaternion_path {
struct Quaternion{double w,x,y,z;};struct Key{double time;Quaternion value;};
Quaternion sample(const std::vector<Key>& keys,double time);std::vector<Quaternion> sample_many(const std::vector<Key>& keys,const std::vector<double>& times);
}

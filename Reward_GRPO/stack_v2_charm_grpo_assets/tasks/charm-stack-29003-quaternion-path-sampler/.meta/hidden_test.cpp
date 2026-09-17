#include "quaternion-path-sampler.h"
#include "test_support.h"
#include <cmath>
#include <limits>
#include <stdexcept>
static bool near(double a,double b){return std::abs(a-b)<1e-10;}
int main(){using namespace quaternion_path;std::vector<Key> k={{0,{2,0,0,0}},{2,{0,0,0,3}},{5,{0,0,2,0}}};auto a=sample(k,-1),b=sample(k,9);CHECK(near(a.w,1)&&near(b.y,1));auto m=sample(k,1);CHECK(near(m.w,std::sqrt(0.5))&&near(m.z,std::sqrt(0.5)));auto exact=sample(k,2);CHECK(near(exact.z,1));auto many=sample_many(k,{4,0,1});CHECK(many.size()==3&&near(many[0].y,std::sqrt(0.75))&&near(many[0].z,0.5)&&near(many[1].w,1)&&near(many[2].w,std::sqrt(0.5)));auto anti=sample({{0,{1,0,0,0}},{1,{-1,0,0,0}}},0.5);CHECK(near(std::abs(anti.w),1));for(auto q:many)CHECK(near(std::hypot(std::hypot(q.w,q.x),std::hypot(q.y,q.z)),1));CHECK_THROWS(std::invalid_argument,sample({},0));CHECK_THROWS(std::invalid_argument,sample({{1,{1,0,0,0}},{1,{1,0,0,0}}},1));CHECK_THROWS(std::invalid_argument,sample({{0,{0,0,0,0}}},0));CHECK_THROWS(std::invalid_argument,sample(k,std::numeric_limits<double>::infinity()));return charm_failures?1:0;}

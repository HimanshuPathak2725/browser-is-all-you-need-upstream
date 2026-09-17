#include "capped-reuse-pool.h"
namespace reuse_pool {Pool::Pool(std::size_t n):slots_(n){}std::optional<Handle> Pool::acquire(){return std::nullopt;}void Pool::release(Handle){}std::size_t Pool::collect(std::size_t){return 0;}std::size_t Pool::live()const noexcept{return live_;}}

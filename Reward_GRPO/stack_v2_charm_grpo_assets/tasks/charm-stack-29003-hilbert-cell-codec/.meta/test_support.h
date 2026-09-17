#pragma once
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <string>
inline int charm_failures = 0;
inline void charm_check(bool ok, const char* expression, int line) {
    if (!ok) { std::cerr << "line " << line << ": " << expression << "\n"; ++charm_failures; }
}
template <class Exception, class Function>
inline void charm_throws(Function&& function, int line) {
    try { function(); } catch (const Exception&) { return; } catch (...) {}
    std::cerr << "line " << line << ": expected exception\n"; ++charm_failures;
}
inline std::uint64_t charm_nonce() {
    const char* text = std::getenv("CHARM_NONCE");
    if (!text) return 0x9e3779b97f4a7c15ULL;
    return static_cast<std::uint64_t>(std::strtoull(text, nullptr, 10));
}
#define CHECK(expr) charm_check(static_cast<bool>(expr), #expr, __LINE__)
#define CHECK_THROWS(type, expr) charm_throws<type>([&] { (void)(expr); }, __LINE__)

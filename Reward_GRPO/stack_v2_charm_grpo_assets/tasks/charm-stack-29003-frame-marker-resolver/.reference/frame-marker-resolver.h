#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>
namespace frame_markers {
struct Frame { std::string name; double duration; std::vector<std::string> markers; };
struct Advance { std::size_t frame; double local_time; std::vector<std::string> crossed; };
Advance advance(const std::vector<Frame>& frames,double from,double delta,bool loop);
std::optional<std::size_t> find_frame(const std::vector<Frame>& frames,std::string_view name);
}

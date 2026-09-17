#include "robot_name.h"

#include <algorithm>
#include <iomanip>
#include <mutex>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace robot_name {
namespace {
std::string generate_name() {
    static std::mutex mutex;
    static const std::vector<unsigned int> names = [] {
        std::vector<unsigned int> values(26 * 26 * 1000);
        std::iota(values.begin(), values.end(), 0u);
        std::random_device seed;
        std::mt19937 engine(seed());
        std::shuffle(values.begin(), values.end(), engine);
        return values;
    }();
    static std::size_t next = 0;
    const std::lock_guard<std::mutex> lock(mutex);
    if (next == names.size())
        throw std::range_error("name combinations exhausted");
    const auto value = names[next++];
    std::ostringstream output;
    output << static_cast<char>('A' + value / 26000)
           << static_cast<char>('A' + (value / 1000) % 26)
           << std::setw(3) << std::setfill('0') << value % 1000;
    return output.str();
}
}  // namespace

robot::robot() : name_(generate_name()) {}

void robot::reset() {
    name_ = generate_name();
}
}  // namespace robot_name

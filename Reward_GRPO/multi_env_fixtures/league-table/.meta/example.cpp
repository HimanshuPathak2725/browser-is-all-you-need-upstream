#include "league_table.h"

#include <algorithm>

namespace league {

bool standing::operator==(const standing& other) const {
    return name == other.name && points == other.points;
}

void table::record(const std::string& name, int points) {
    points_[name] += points;
}

int table::points_for(const std::string& name) const {
    const auto found = points_.find(name);
    return found == points_.end() ? 0 : found->second;
}

std::vector<standing> table::standings() const {
    std::vector<standing> result;
    for (const auto& item : points_) {
        result.push_back({item.first, item.second});
    }
    std::sort(result.begin(), result.end(), [](const standing& left,
                                                const standing& right) {
        if (left.points != right.points) {
            return left.points > right.points;
        }
        return left.name < right.name;
    });
    return result;
}

std::size_t table::teams() const {
    return points_.size();
}

}

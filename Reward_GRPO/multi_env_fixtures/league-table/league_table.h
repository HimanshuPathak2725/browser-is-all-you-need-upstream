#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace league {

struct standing {
    std::string name;
    int points;
    bool operator==(const standing& other) const;
};

class table {
  public:
    void record(const std::string& name, int points);
    int points_for(const std::string& name) const;
    std::vector<standing> standings() const;
    std::size_t teams() const;

  private:
    std::map<std::string, int> points_;
};

}

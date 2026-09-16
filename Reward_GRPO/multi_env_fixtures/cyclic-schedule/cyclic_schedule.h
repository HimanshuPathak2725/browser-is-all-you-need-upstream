#pragma once

#include <string>

namespace cyclic_schedule {

class weekly_time {
  public:
    static weekly_time at(int weekday, int hour, int minute = 0);
    weekly_time& advance(long long minutes);
    weekly_time& rewind(long long minutes);
    int weekday() const;
    int hour() const;
    int minute() const;
    std::string str() const;
    bool operator==(const weekly_time& other) const;

  private:
    explicit weekly_time(long long minute_of_week);
    long long minute_of_week_{0};
};

}

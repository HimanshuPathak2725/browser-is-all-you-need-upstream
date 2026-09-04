#include "cyclic_schedule.h"

#include <iomanip>
#include <sstream>

namespace cyclic_schedule {

weekly_time::weekly_time(long long minute_of_week)
    : minute_of_week_(minute_of_week) {}

weekly_time weekly_time::at(int weekday, int hour, int minute) {
    return weekly_time((static_cast<long long>(weekday) * 24 + hour) * 60 + minute);
}

weekly_time& weekly_time::advance(long long minutes) {
    minute_of_week_ += minutes;
    return *this;
}

weekly_time& weekly_time::rewind(long long minutes) {
    minute_of_week_ -= minutes;
    return *this;
}

int weekly_time::weekday() const { return static_cast<int>(minute_of_week_ / 1440); }
int weekly_time::hour() const { return static_cast<int>((minute_of_week_ / 60) % 24); }
int weekly_time::minute() const { return static_cast<int>(minute_of_week_ % 60); }

std::string weekly_time::str() const {
    std::ostringstream out;
    out << 'D' << weekday() << ' ' << std::setw(2) << std::setfill('0')
        << hour() << ':' << std::setw(2) << minute();
    return out.str();
}

bool weekly_time::operator==(const weekly_time& other) const {
    return minute_of_week_ == other.minute_of_week_;
}

}

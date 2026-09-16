# Weekly schedule point

Implement `cyclic_schedule::weekly_time` in `cyclic_schedule.h` and
`cyclic_schedule.cpp`.

The object represents a minute in a repeating seven-day week. Weekdays are
numbered `0` through `6`, and its string form is exactly `D<day> HH:MM`.
`at()`, `advance()`, and `rewind()` must normalize arbitrary positive or
negative offsets across hour, day, and week boundaries. Mutating operations
return `*this` so calls can be chained.

Preserve this public API:

```cpp
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
};
}
```

Return complete whole-file listings for both editable files.

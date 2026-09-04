# Instructions

Given an age in seconds, calculate how old someone would be on a planet in our Solar System.

One Earth year equals 365.25 Earth days, or 31,557,600 seconds.
If you were told someone was 1,000,000,000 seconds old, their age would be 31.69 Earth-years.

For the other planets, you have to account for their orbital period in Earth Years:

| Planet  | Orbital period in Earth Years |
| ------- | ----------------------------- |
| Mercury | 0.2408467                     |
| Venus   | 0.61519726                    |
| Earth   | 1.0                           |
| Mars    | 1.8808158                     |
| Jupiter | 11.862615                     |
| Saturn  | 29.447498                     |
| Uranus  | 84.016846                     |
| Neptune | 164.79132                     |

~~~~exercism/note
The actual length of one complete orbit of the Earth around the sun is closer to 365.256 days (1 sidereal year).
The Gregorian calendar has, on average, 365.2425 days.
While not entirely accurate, 365.25 is the value used in this exercise.
See [Year on Wikipedia][year] for more ways to measure a year.

[year]: https://en.wikipedia.org/wiki/Year#Summary
~~~~


## C++ interface contract

The test file is not shown to you, so the interface it expects is stated here in
full. Implement exactly these names and signatures; the tests use nothing else.

```cpp
namespace space_age {
class space_age {
public:
    explicit space_age(unsigned long long seconds);
    unsigned long long seconds() const;
    double on_earth() const;
    double on_mercury() const;
    double on_venus() const;
    double on_mars() const;
    double on_jupiter() const;
    double on_saturn() const;
    double on_uranus() const;
    double on_neptune() const;
};
}
```

The class and its namespace are both named `space_age`. The constructor is `explicit`. Results are compared with a floating-point tolerance.

## Build environment

- The exercise is compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, so
  any warning fails the build.
- Only `space_age.h` and `space_age.cpp` are editable. `CMakeLists.txt` and the test
  file are fixed and must not be modified.
- The test file includes only `space_age.h`, so every name above must be visible
  from that header.
- You may either declare in `space_age.h` and define in `space_age.cpp`, or define
  everything `inline`/in-class in `space_age.h` and leave `space_age.cpp` unchanged.
  Both are accepted.

# Instructions

Manage robot factory settings.

When a robot comes off the factory floor, it has no name.

The first time you turn on a robot, a random name is generated in the format of two uppercase letters followed by three digits, such as RX837 or BC811.

Every once in a while we need to reset a robot to its factory settings, which means that its name gets wiped.
The next time you ask, that robot will respond with a new random name.

The names must be random: they should not follow a predictable sequence.
Using random names means a risk of collisions.
Your solution must ensure that every existing robot has a unique name.


## C++ interface contract

The test file is not shown to you, so the interface it expects is stated here in
full. Implement exactly these names and signatures; the tests use nothing else.

```cpp
namespace robot_name {
class robot {
public:
    robot();
    std::string const& name() const;
    void reset();
};
}
```

A name is two uppercase letters followed by three digits, e.g. `"RX837"`. `reset()` assigns a new name. The tests create many robots and require all names to be distinct, so issued names must never repeat.

## Build environment

- The exercise is compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, so
  any warning fails the build.
- Only `robot_name.h` and `robot_name.cpp` are editable. `CMakeLists.txt` and the test
  file are fixed and must not be modified.
- The test file includes only `robot_name.h`, so every name above must be visible
  from that header.
- You may either declare in `robot_name.h` and define in `robot_name.cpp`, or define
  everything `inline`/in-class in `robot_name.h` and leave `robot_name.cpp` unchanged.
  Both are accepted.

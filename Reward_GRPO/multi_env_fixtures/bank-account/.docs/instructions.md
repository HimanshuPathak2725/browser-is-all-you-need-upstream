# Instructions

Your task is to implement bank accounts supporting opening/closing, withdrawals, and deposits of money.

As bank accounts can be accessed in many different ways (internet, mobile phones, automatic charges), your bank software must allow accounts to be safely accessed from multiple threads/processes (terminology depends on your programming language) in parallel.
For example, there may be many deposits and withdrawals occurring in parallel; you need to ensure there are no [race conditions][wikipedia] between when you read the account balance and set the new balance.

It should be possible to close an account; operations against a closed account must fail.

[wikipedia]: https://en.wikipedia.org/wiki/Race_condition#In_software


## C++ interface contract

The test file is not shown to you, so the interface it expects is stated here in
full. Implement exactly these names and signatures; the tests use nothing else.

```cpp
namespace Bankaccount {
class Bankaccount {
public:
    void open();
    void deposit(int amount);
    void withdraw(int amount);
    void close();
    int balance();
};
}
```

Note the namespace and class name are both `Bankaccount` (capital B, one word), not `bank_account`.

Every misuse throws `std::runtime_error`: opening an already-open account, closing or using an account that is not open, depositing or withdrawing a non-positive amount, and withdrawing more than the balance.

A newly opened account has a zero balance. After `close()`, a later `open()` starts a fresh account at zero; the previous balance is not retained.

The tests call `deposit` and `withdraw` concurrently from many `std::thread`s on one account, so the class must be internally thread-safe.

## Build environment

- The exercise is compiled as C++17 with `-Wall -Wextra -Wpedantic -Werror`, so
  any warning fails the build.
- Only `bank_account.h` and `bank_account.cpp` are editable. `CMakeLists.txt` and the test
  file are fixed and must not be modified.
- The test file includes only `bank_account.h`, so every name above must be visible
  from that header.
- You may either declare in `bank_account.h` and define in `bank_account.cpp`, or define
  everything `inline`/in-class in `bank_account.h` and leave `bank_account.cpp` unchanged.
  Both are accepted.

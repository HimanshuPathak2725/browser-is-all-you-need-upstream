# League table

Implement `league::table` in `league_table.h` and `league_table.cpp`.
`record(name, points)` accumulates a team's points and accepts positive,
zero, or negative adjustments. `points_for()` returns zero for an unknown
team. `standings()` returns one `standing` per known team, ordered by
descending points and then lexicographically ascending name. `teams()`
returns the number of distinct recorded names.

Preserve the declared public API and return complete whole-file listings for
both editable files.

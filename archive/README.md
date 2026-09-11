# Archive

Superseded working material, kept for provenance. Nothing here is part of the build, and
nothing in the repository reads these files.

Files are stored **verbatim**, exactly as they were when captured. Their contents are not
corrected or brought up to date, so they may describe an older design, use names that have
since changed, or refer to documents that are not in this repository.

## robert-taxonomy-2026-09-01.yaml

An earlier design of the tag vocabulary, captured 1 September 2026. It is in two parts —
`categories`, a browse-only first-level classification never assigned to an RFC, and `tags`,
at most two levels deep, each carrying `aliases`, classifier `match` regexes and working
group `groups`. The current system in `taxonomy.yaml` differs: it has no browse-only layer,
every level is assignable, and it reaches four levels.

It is cited as the `source` of every row in `alias-candidates.csv`, which is where the alias
candidates held for review came from.

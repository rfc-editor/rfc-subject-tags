# Curation tools

Tools a curator runs by hand, and the record of the pass that produced the
`aliases` now in `taxonomy.yaml`. Nothing here is part of the build: the
published pipeline neither reads nor executes any of it.

## What produced the alias set

`alias_pass.py` asks a model once per tag what else that tag answers to, and
checks every proposal against the corpus before keeping it. It exists because
neither existing field can hold an alias. `desc` is the display text and carries
one name and one expansion; `match` decides which RFCs get a tag and is never
searched. A reader typing SNTP, SSL or SMIv2 reached nothing, even though
`match` already contained some of those strings.

```sh
pip install -r ../requirements.txt -r requirements.txt
python3 alias_pass.py --dry-run --limit 3      # render prompts, no calls
python3 alias_pass.py                          # full pass, resumable
python3 alias_pass.py --report                 # rebuild outputs, no calls
python3 merge_aliases.py                       # write ../taxonomy.yaml
```

It needs `rfcs.json` for grounding — a build product, not in the repository, so
either run `python3 ../make_corpus_from_index.py` or fetch the snapshot the last
build published:

```sh
curl -O https://rfc-editor.github.io/rfc-subject-tags/rfcs.json
```

Two backends: `--backend api` uses `ANTHROPIC_API_KEY`; `--backend cli` uses an
existing Claude Code login and needs no key, at roughly three times the
equivalent cost and without schema-guaranteed output.

## Grounding: full text, then precision

Proposals are checked against the **full-text corpus** — the `rfcNNNN.txt`
files — via `--fulltext DIR`, falling back to `rfcs.json` metadata when that
directory is absent. Metadata alone is not enough: `krb5`, `authz`, `RadSec`,
`tcpdump`, `EBNF` and about a hundred others appear only in RFC bodies, and a
metadata-only check rejects every one.

A raw full-text count is not enough either, because a short string matches for
unrelated reasons. `h2` appears in 202 RFCs, nearly all of them HTML headings,
hosts H1/H2/H3 in topology diagrams, or IP octets `h1.h2.h3.h4`. So each term
is scored on precision:

| | |
|---|---|
| `raw` | documents containing the term |
| `ctx` | of those, the ones the tag's own `match` rules also fire on |
| `%` | precision, `ctx/raw` |

A proposal is kept with at least one in-context hit and precision at or above
`--min-precision` (default 20). Measured this way `disruption` under `DTN`
scores 2% and `h2` scores 5%, while genuinely short abbreviations hold up —
`TE` 71%, `PW` 72%, `ND` 78%. **Length is not the discriminator; precision is.**
A rule excluding two-character terms would have cost `TE`, `PW`, `ND`, `SR` and
six more while keeping `LAG` and `DoS`, which are longer and less precise.

The threshold is deliberately low. Between 20% and 50% genuine and spurious
terms are mixed — `X11` at 31% is real, `LAG` at 36% was not — so that band is
kept and surfaced with its numbers rather than filtered blind. The **Aliases**
view in `rfc-tags.html` is where that reading happens.

**Precision measures topical co-occurrence, not naming.** It cannot tell "sftp
is another name for ftp" from "sftp is discussed alongside ftp": `sftp` scores
100% against `FTP` and 10% against `SSH`, yet SFTP *is* the SSH File Transfer
Protocol. That judgement is a reading, not a measurement, and `sftp` is recorded
on `SSH` as a manual override. Rule-1 errors generally survive the filter, so
the rejection list in `review.md` is a review queue, not a discard pile.

## Outputs

| File | What it is |
|---|---|
| `aliases.yaml` | the alias set as merged into `taxonomy.yaml`, with each term's counts and the reason it was kept |
| `results.jsonl` | one raw response per tag; also the resume file |
| `review.md` | everything needing a human: rejections, ambiguities, collisions, candidates |
| `promotions.yaml` / `promotions.jsonl` | the tag/alias/drop decisions described below |

`merge_aliases.py` writes through the dumper `regen.py` uses, so the diff
contains only the added blocks and the next regen reformats nothing. Running it
against `taxonomy.yaml` reproduces the alias field exactly.

### Re-running the pass

**A model pass is not deterministic.** A re-run explores a different subset
rather than reproducing the last one — the run that introduced the tag/alias
split found 581 entries against the previous 485, but 82 terms the earlier pass
had proposed were simply absent. Nothing judged them; that pass went a different
way. So compare against the last output on every re-run:

```sh
git show HEAD:curation/aliases.yaml > /tmp/prev.yaml
python3 alias_pass.py --previous /tmp/prev.yaml ...
```

Terms the previous pass proposed and this one did not are listed in `review.md`
under *Proposed by a previous pass, not re-proposed*, and the section carries
its own entries forward until someone acts on them. This is why only one
`results.jsonl` is kept: the useful artefact is the difference between passes,
and git already holds every committed `aliases.yaml` to difference against.

## promote_pass.py and apply_promotions.py — superseded

These answered the question the alias pass leaves behind: is a term another name
for its tag, or a technology of its own? They sorted 260 candidates into 88 tags,
161 aliases and 11 drops, using R11's evidence test — does an RFC title use the
name as the name of the thing — with the count as a prefilter and the model as
the decision, because counting alone promotes `IAB` at 69 title hits and cannot
separate `SHA-256` from `ECDSA`.

**The vocabulary work on `main` reached the same place independently and went
further**, promoting 93 technologies including six these tools missed. The tags
in `taxonomy.yaml` are `main`'s, not these; `tag_candidates.py` at the
repository root is the maintained version of the harvester this pass fed on.
They are kept here as the record of how the alias set was separated from the tag
set, and because the reasons in `promotions.yaml` explain why particular terms
are aliases rather than tags. For new work, use `tag_candidates.py`.

## Reviewing the result

`aliases.yaml` is a record, not an assertion. Each line carries the model's
reason and the term's counts, which is usually enough to judge in seconds. The
failure mode to watch for is a term naming a *different* technology rather than
the same one by another name — that produces a confidently wrong search hit
where today the reader correctly falls through to full-text search. The Aliases
view in the published page is built for exactly that reading.

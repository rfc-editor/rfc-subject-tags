# RFC Subject Tags — Code and Outputs

How the tag system is built: the input corpus, the taxonomy file, the tagger that assigns tags, the derivation of the served view, and every file the pipeline produces. Aims, requirements and semantics are in README.md; acceptance checks and figures are in validation.md.

## Files at a glance

### Normative (edit this)

| File | Contains |
|---|---|
| `assignments.yaml` | Hand assignments: one entry per RFC a person has corrected or confirmed — tags to add or remove, a reason, who and when. Applied after the model's assignment; a document with an entry is reviewed. Currently empty: the entries that corrected the former rule engine were removed with it |
| `tagging_instructions.md` | What the model is told: what a tag means, how to choose, and what to return. The taxonomy is appended to it at run time. Changing it changes what the next tagger run assigns |
| `taxonomy.yaml` | Every tag with its parent, kind, description, decomposition and implied topics. Each entry also carries a generated `stats` block (see below) that `regen.py` rewrites and curators do not edit |

### Code

| File | Purpose |
|---|---|
| `tagger.py` | Has a model read each RFC with the taxonomy and choose its tags with reasons; applies the hand assignments; writes `rfc-tags.json`. Needs the `claude` command-line program and the RFC texts (see Assignment) |
| `engine.py` | Reads and validates `taxonomy.yaml` and `assignments.yaml`; derives paths and the two-axis view. Used by `tagger.py` and `regen.py` |
| `make_corpus_from_index.py` | Builds `rfcs.json` from the RFC Editor's `rfc-index.xml`, downloading it if absent |
| `make_corpus_from_local.py` | Builds `rfcs.json` from a directory of per-RFC metadata files instead |
| `regen.py` | Regenerates the generated files, assigns missing `uuid`s and regenerates `slug`s, writes those and the `stats` blocks into `taxonomy.yaml`, and refreshes the figures in validation.md and README.md and the generated blocks in this file |
| `tag_candidates.py` | Harvests names that RFC titles introduce beside their expansion and that no tag makes reachable — candidates for absorbed technologies (R10); runs on every build, judges nothing |
| `browser_template.html` | The review page (five views: Vocabulary, Co-occurrence, Lifespan, Overlap, All RFCs) with its data removed; `regen.py` embeds the current data to produce `rfc-tags.html`. Fonts are embedded so the page works offline |

### Generated (never edit by hand)

`rfc-tags.json` is tracked in the repository: it is the record of every assignment and the
reasoning for it, and a change to it is reviewed like any other. The rest are gitignored build
products. A local run produces them in the working directory, and CI publishes the current
build to GitHub Pages:

| Artifact | Published at |
|---|---|
| `rfc-tags.html` | <https://rfc-editor.github.io/rfc-subject-tags/> |
| `rfc-tags.json` | <https://rfc-editor.github.io/rfc-subject-tags/rfc-tags.json> |
| `rfc-tags.csv` | <https://rfc-editor.github.io/rfc-subject-tags/rfc-tags.csv> |
| `rfcs.json` | <https://rfc-editor.github.io/rfc-subject-tags/rfcs.json> |

The build runs daily, so the published page tracks the current corpus. The figures committed in
README.md and validation.md describe the last curation run instead, and drift from it as RFCs
publish; the page carries its own build date so the two can be told apart.

| File | Contents |
|---|---|
| `rfcs.json` | Corpus metadata, one record per RFC — the list of RFCs to tag, produced by either corpus script. Fetched fresh at build time; the snapshot each build used is published alongside the other artifacts, so a published build can be reproduced exactly |
| `rfc-tags.json` | Per RFC, keyed `RFCn` in number order: `title`, `year`; `summary` (the model's one sentence on what the document is); `tags` (ids); `reasons` (per tag: `role` `primary` or `secondary`, `why`, a `quote` from the document and its `section`; for a hand assignment `role` is `hand` with `why`, `by` and `date`, and a tag both chose carries the model's fields plus a `hand` object); `rejected` (tags the model considered and decided against, each with `why`); `gaps` (subjects the model found no tag for); `review` (what a person should check; empty if nothing); `reviewed` (true when `assignments.yaml` has an entry); full `paths` (R4) as arrays of ids; `technology` / `topic` coordinates for the served view; and `tagged` (the `model`, `date` and `prompt` hash of the run, its `notes`, the `tags` the model chose before hand assignments, and its reasoning for any that were `removed`), or null if the model has not tagged the RFC |
| `rfc-tags.csv` | The same table for spreadsheet use; list fields are `;`-separated, paths `|`-separated with ids joined by ` / ` |
| `tag-candidates.json` | Output of `tag_candidates.py`: candidate names by tag, most-seen first, with example RFCs |
| `rfc-tags.html` | Self-contained review page. **Vocabulary**: the tree with corpus count and notifications-per-year (since 2021) per tag, search, technology/topic filter, multi-select with AND/OR and the matching RFCs. **Co-occurrence**: tag pairs sharing RFCs. **Lifespan**: each tag's first-to-last year, live or dormant. **Overlap**: Jaccard and one-way overlap flags for redundant or nested pairs. **All RFCs**: look-up with tags and served technology/topic coordinates |

### To reproduce

```
pip install -r requirements.txt                          # PyYAML, the only dependency
python3 make_corpus_from_index.py                        # rfcs.json from rfc-index.xml (downloads it)
#   or: python3 make_corpus_from_local.py ~/Data/RFCs rfcs.json
python3 tagger.py                                        # tags RFCs that rfc-tags.json has no result for; needs model access
#   or: python3 tagger.py --no-model                     # no model: bring rfc-tags.json up to date with the other files
python3 regen.py                                         # rendered files and document figures
python3 tag_candidates.py                                # tag-candidates.json for the next vocabulary review
```

Every step reads and writes in the working directory. A full run leaves `rfc-index.xml`,
`rfcs.json`, `rfc-tags.csv` and `rfc-tags.html` beside the sources as gitignored build products,
and updates the tracked `rfc-tags.json`.

Then run the checks in validation.md.

## Corpus

### Record format

One record per published RFC:

| Field | Notes |
|---|---|
| `id` | `RFC9000` |
| `title` | |
| `year`, `month` | |
| `day` | Present only when the source records a day of month — see below |
| `keywords` | Author keywords |
| `abstract` | |
| `wg` | Producing working group, lower-cased; absent for non-WG streams |
| `stream`, `status` | Informational only |

### Sources

- The rfc-editor.org index (`rfc-index.xml`), parsed to `rfcs.json` by `make_corpus_from_index.py`. <!-- generated:coverage -->Coverage: 9,869 RFCs; 7,276 with a working group; 7,458 with keywords; 9,162 with abstracts.<!-- /generated -->
- A local directory of per-RFC `.json` files, via `make_corpus_from_local.py`. It expects one file per RFC, named `rfcNNNN.json`; the script defaults to `~/Data/RFCs` and takes the directory as its first argument. Field names vary between sources, so the script's `FIELD_MAP` is configurable — for example, the producing group may be under `source` rather than `wg`.

### The `day` assumption

In the rfc-editor index only the April 1st series carries a day of month: 71 documents, 63 dated exactly 1 April and the rest adjacent-day entries of the same series. Nothing in the pipeline depends on it now: whether a document is humorous is the model's judgement from the text (the former rule engine used the presence of `day` as its humor test).

## The taxonomy file

`taxonomy.yaml` has two top-level keys: `version` and `tags`, a list in tree order. Version 2.0.0 removed what only the former rule engine read: the `engine` parameter block and the per-tag `match`, `match_title_only`, `groups`, `streams`, `yields_to`, `documents` and `max_year` fields. Everything known about a tag is in its one entry.

### Tag entry

```yaml
- id: DKIM                       # written as the documents write it; unique case-insensitively
  uuid: 5b3c8f2e-...             # generated once by regen.py; never changes, even when the id is renamed
  slug: dkim                     # generated by regen.py from the id (Django slugify); URL-safe form
  parent: email-authentication   # omitted for roots
  kind: technology               # or topic; roots must be topic
  desc: DKIM (DomainKeys Identified Mail)   # the model reads this: it defines the tag's scope
```

Optional fields:

| Field | Meaning |
|---|---|
| `uuid` | **Generated, permanent.** A version-4 UUID assigned by `regen.py` to any tag that lacks one, and then never changed. It is the tag's identity across renames: rename the `id`, keep the `uuid`. Unique. |
| `slug` | **Generated, derived.** Django's `slugify` applied to the id (`HTTP/2` → `http2`, `.onion` → `onion`, `congestion control` → `congestion-control`), with each `+` first written as `p` (`WHOIS++` → `whoispp`, `TACACS+` → `tacacsp`, as C++ is written cpp), and any remaining repeat deduplicated in file order with `-2`, `-3`. Regenerated on every run, so it follows a rename. The loader rejects a slug that differs from what it would generate. |
| `implies` | Topics this technology entails by purpose (R20), added in the served view |
| `decomposes_to` | For the six composite topics: the topics they split into in the served view |
| `stats` | **Generated.** `direct`, `total`, `first_year`, `last_year`, and for served topics `served`. Rewritten by `regen.py`; the browser's lifetime view reads `first_year`/`last_year` |

Description convention: the correct-case name, the expansion in parentheses for acronyms, then the scope, with no repetition of the name or expansion. See README.md.

### Validation on load

`engine.Taxonomy` refuses a file that has:

- an id outside the allowed form — letters, digits, single spaces and `. _ / + -`, none leading or trailing, ASCII only — or containing the path separator ` / `;
- two ids that would be confused with each other: the same after case-folding, Unicode normalisation and whitespace collapsing;
- a parent, `implies` or `decomposes_to` reference to a tag that does not exist (references are exact);
- a tag without a `uuid`, a `uuid` that is not version 4, or two tags sharing one; a `slug` that is not what `slugify` derives from the id (`regen.py` loads with `require_ids=False` to assign them, then re-loads strictly);
- a root that is not a topic, or a kind other than `technology`/`topic`;
- a path deeper than four levels;
- a catch-all name (`misc`, `other`, `general`).

### Identity of an id

Stored references and data files use ids exactly as written: `parent: IPv6` names the tag `IPv6` and nothing else. Uniqueness is stricter than that on purpose — two ids that differ only in case or spacing would be indistinguishable to a reader, so the loader refuses them — and that stricter test is also how user input is matched: `Taxonomy.lookup(text)` resolves `ipv6`, `Congestion  Control` or `http/2` to the stored id, or `None`. It is the one place case-insensitive matching happens; consumers matching user input should call it rather than compare strings themselves. The page's search applies the same folding.

The character rule exists because ids appear inside other formats: ` / ` joins the ids of a path in `rfc-tags.csv` and the page, `;` and ` | ` delimit lists in the CSV, and the page places ids in HTML text and attributes (which it escapes regardless).

### Editing the file

| To | Do |
|---|---|
| Add a technology | Add an entry with `parent`, `kind: technology` and `desc`. Its subject topic follows from its root automatically. No existing RFC gains the tag until it is tagged again: `tagger.py --retag` the documents it should apply to. |
| Add a topic | Add an entry with `kind: topic` and `desc`; add it to `implies` on technologies whose purpose it is. |
| Move a tag between axes | Change `kind` — one word. (Breaking once subscriptions exist; see README.md.) |
| Split a tag | Add children with `parent` set to it; keep the parent. |
| Rename a tag | Change `id` and every reference to it (`parent`, `implies`, `decomposes_to`); **keep the `uuid` line**. `rfc-tags.json` holds ids too: rename them there or `--retag` the documents that carry the tag, or they are flagged as carrying a tag no longer in the taxonomy. Run `regen.py`: the slug follows the new id, the uuid does not change. A serving layer that keys on `uuid` needs no redirect; one that keys on `slug` should redirect the old slug. |

## Assignment

`tagger.py` assigns tags. For each RFC it sends a model the instructions in `tagging_instructions.md`, the taxonomy (each tag's id, kind and description, as an indented tree) and the full text of the RFC, and gets back the tags the document is about, with the reasoning for each.

### What it needs

- **The model.** `tagger.py` runs the `claude` command-line program (Claude Code) once per RFC. Each person running the tagger installs it and signs in with their own account, or sets `ANTHROPIC_API_KEY`; the repository holds no credentials and CI calls no model. The model is `claude-sonnet-5-5` at medium effort, the combination the instructions were tested with; `--model` overrides it.
- **The RFC texts.** `rfcNNNN.txt` files in a local copy of the corpus, by default `~/Data/RFCs` (`--corpus` or `$RFC_CORPUS`). Keep the copy current with `rsync -av rsync.rfc-editor.org::rfcs ~/Data/RFCs`; do not fetch RFCs one by one over HTTP. An RFC with no text file is left untagged and listed at the end of the run.

### What a run does

1. **Chooses the RFCs.** By default, every RFC in `rfcs.json` for which `rfc-tags.json` holds no model result: after an index refresh, the newly published ones. `--retag RFC9000 RFC9001` tags the named RFCs again; `--all` tags the whole corpus again; `--limit N` stops after N.
2. **Asks the model**, one RFC per fresh context, `--jobs` at a time (default 6). Text beyond 300,000 characters is cut off.
3. **Checks the answer.** A tag id the taxonomy does not have is dropped. Each quote is looked for in the text, ignoring page headers and footers, line breaks, spacing and punctuation. Both leave a note in `review`. `--no-model --recheck` repeats the quote check for every stored result, for use after the check itself changes.
4. **Applies hand assignments.** The RFC's entry in `assignments.yaml`, if any: `remove` tags are taken out, `add` tags put in.
5. **Derives** `paths`, `technology` and `topic` (below) and writes `rfc-tags.json`.

Steps 4 and 5 run for every RFC on every run, from what `rfc-tags.json` already holds; `--no-model` runs only those. A model result is therefore kept until someone asks for that RFC to be tagged again. Changing `tagging_instructions.md`, or a tag's description, does not by itself change any assignment: each entry records the hash of the prompt it was produced with (`tagged.prompt`), and re-tagging is a decision.

Results are saved in `.tagger-cache/` as they arrive, so an interrupted run resumes where it stopped. The run stops by itself after five consecutive failures (signed out, usage limit reached).

A run over the whole corpus sends every RFC's text to the model: budget for it. The first full run (9,836 RFCs, November 2026) reported $893, about $0.09 per RFC, and on a subscription took five 5-hour usage windows.

### What the tagger does not decide

The model's list is kept as given, in its order, apart from the checks above. In particular a tag may sit beside its own ancestor when the model judged the document to be about both. Nothing enforces R16: a document tagged `humor` beside other tags gets a review reason, not a correction.

Every RFC's `review` list says what a person should check: the model has not tagged it; a quote was not found in the text; the text was cut; the model chose a tag that does not exist, or one since removed from the taxonomy; the result has no tags (R7), no topic (R8) or `humor` beside other tags (R16); or it shares no tag, counting ancestors, with the RFC that obsoletes it or that it obsoletes. An empty list does not mean the assignment is right.

`closure(tags)` expands tags to their root-anchored paths, which appear as `paths` in `rfc-tags.json` (R4).

## Recording a review

The model proposes; a person confirms (README, Search and subscription semantics). The reasoning in `rfc-tags.json` is there to be checked. A correction is recorded in `assignments.yaml`:

```yaml
overrides:
  RFC3930:
    add: [internet architecture]
    reason: Title-specific essay on protocol design
    by: jd
    date: 2026-09-30
```

An entry may confirm the model's result with no `add` or `remove` at all; what matters is that the document has been looked at. The loader rejects an entry naming a tag that does not exist or lacking a reason. Run `tagger.py --no-model` to apply the change. When wrong assignments form a *class* of documents, the fix belongs in `tagging_instructions.md` or in the tag's description, followed by `--retag` of the documents affected.

The page's Review tab lists the documents with review reasons, filterable by reason, and the RFC card marks each tag as the model's primary or secondary subject or a hand assignment; the page reports, it does not edit `assignments.yaml`.

## Served view

`engine.Taxonomy.two_axis(tags)` turns leaf tags into technology × topic coordinates:

1. Take the closure of the leaf tags.
2. Send each tag to the axis its `kind` names. Roots are topics and closure always includes the root, so every document's subjects are the roots of its paths.
3. Replace composite topics by their `decomposes_to` targets.
4. Add each tag's `implies` topics (R20). Technologies imply the topic that is their purpose; a topic may imply another — the `cryptography` root implies `security`.

Nothing is decided by hand at this stage; editing `taxonomy.yaml` and re-running re-derives the whole corpus.

### The composites

<!-- generated:composites -->
| Composite tag | Becomes |
|---|---|
| `DNS privacy` | `privacy` |
| `web security` | `security` |
| `email authentication` | `security` + `authentication` |
| `routing security` | `security` |
| `multicast security` | `multicast` + `security` |
| `operational security` | `security` + `network management` |
<!-- /generated -->

### Implication, by topic

<!-- generated:implies -->
| Topic | Implied by |
|---|---|
| `security` | DNSSEC, DANE, cookies, HSTS, token binding, STIR, SRTP, SFrame, RPKI, BGPsec, tcpcrypt, SEND, SAVI, TEEP, supply chain integrity, cryptography, OSCORE, EDHOC, firmware update, MUD |
| `authentication` | HTTP authentication, STIR, Kerberos, GSS-API, SASL, EAP, PANA, AAA, RADIUS, Diameter, TACACS+, SCIM, federated authentication, Ident, OTP, PAKE |
| `IoT` | TEEP, CoAP, OSCORE, SenML, SDF, 6LoWPAN, RPL, 6TiSCH, LPWAN, SCHC, EDHOC, firmware update, MUD |
| `multicast` | PIM, IGMP, MLD, MSDP, MOSPF, SSM, AMT, BIER, FLUTE, NORM, MVPN |
| `network management` | BMP, SNMP, MIB, AgentX, NETCONF, RESTCONF, YANG, syslog, I2RS, OVSDB |
| `IPv6 transition` | DNS64, NAT64, 6to4, Teredo, DS-Lite, MAP, 6rd, 464XLAT, happy eyeballs |
| `tunneling` | MASQUE, pseudowire, VXLAN, Geneve, GRE, IP-in-IP, L2TP |
| `congestion control` | ECN, AQM, CoDel, PIE, LEDBAT, PCN, ConEx |
| `performance measurement` | RMON, OWAMP, TWAMP, STAMP, LMAP, IPFIX, packet capture |
| `privacy` | DoH, DoT, oblivious DNS, MASQUE, oblivious HTTP, privacy pass |
| `internationalization` | IDN, EAI, UTF-8, Unicode, language tags, PRECIS |
| `QoS` | DetNet, RSVP, Diffserv, Intserv, NSIS, COPS |
| `IP mobility` | MANET, Mobile IPv4, Mobile IPv6, PMIPv6, NEMO, HIP |
| `compression` | ROHC, DEFLATE, gzip, Brotli, zstd, IPComp |
| `authorization` | OAuth, GNAP, XACML, ACE |
| `transport mapping` | DoH, DoT, HTTP/3 |
| `NAT traversal` | ICE, STUN, TURN |
| `time synchronization` | NTP, PTP, time zones |
| `storage` | NFS, iSCSI, RDMA |
| `service discovery` | DNS-SD, SLP |
| `reliable multicast` | FLUTE, NORM |
| `traffic engineering` | RSVP-TE, PCE |
| `routing architecture` | LISP, ILNP |
| `multihoming` | Shim6, HIP |
| `calendaring` | iCalendar, CalDAV |
| `OAM` | BFD |
| `header compression` | ROHC |
| `addressing` | SLAAC |
| `routing` | RPL |
<!-- /generated -->

The `implies` field is consulted over the ancestor closure, so `DKIM` inherits `security` through `email authentication`. Two things the tables do not show because closure supplies them: every tag under the `security` root reaches `security` without an `implies` entry, and a composite's technology context (`DNS` for `DNS privacy`) arrives as its ancestor.

## Regeneration

`regen.py` assigns a `uuid` to any tag without one, regenerates every `slug`, computes each tag's `stats` block, and writes all three back into `taxonomy.yaml`; renders `rfc-tags.csv`; builds `rfc-tags.html` by embedding into `browser_template.html` the tags (with `stats`, notification rate and lifetime), every RFC's row (leaf tags and served coordinates), and tag co-occurrence pairs; and refreshes the figures in validation.md and README.md. Run it after `tagger.py`, after any change to the YAML.

Everything is read and written in the working directory. Three tracked files are rewritten **in place** — `taxonomy.yaml` (its `stats` blocks), `README.md` and `validation.md` (their figures) — so run it on a clean working tree and review the resulting diff as part of the change. The figures move whenever the corpus does: a run against an index one RFC newer than the last shifted two lines of validation.md and 24 lines of `stats`.

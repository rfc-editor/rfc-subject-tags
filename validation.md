# RFC Subject Tags — Validation

The checks a rebuild must pass, and the figures from the current build. Each check names the requirement in README.md it serves. The figures section is rewritten by `regen.py`.

## Checks

### Structural (R3, R5, R12)

`engine.Taxonomy('taxonomy.yaml')` loads without error. It asserts:

- every id unique, and every `parent`, `yields_to`, `implies` and `decomposes_to` reference resolves;
- depth at most four levels;
- every root is a topic;
- no catch-all names.

### Coverage (R7, R8)

- No RFC without a tag.
- In the served view, no RFC without a topic.

### Budget (R4, R6)

- Every assignment is emitted as full paths.
- Mean tags per RFC, counting ancestors, is between 1 and 10.
- Report the distribution and the maximum.

### Humor (R16)

Both directions:

- every `humor` document carries nothing else;
- every day-dated document, and every RFC listed in the `humor` tag's `documents` field, carries `humor`.

### Unused and single-document tags (R9, R13)

- No tag is carried by zero documents — such a tag is either mis-ruled or should not exist.
- List tags carried by exactly one document for review against R13.

### Stability replay (R17, R18)

1. Sort the corpus by (year, month, RFC number).
2. Record each tag's first appearance.
3. Report the distribution of new-tags-per-RFC and list every RFC that debuts two or more.
4. Repeat on the topic axis alone and list debuts after 2003.

### Spot checks (R19, R20)

A fixed list of well-known RFCs with expected results:

| RFC | Expected |
|---|---|
| 791 | `IPv4` |
| 793 | `TCP` |
| 822 | `message format` |
| 1034 | `DNS` |
| 2616 | `HTTP` |
| 8446 | `TLS` |
| 9000 | `QUIC`, `UDP` — topic `transport` only |
| 7748 | `elliptic curve` — topics `cryptography` and `security` |
| 9001 | `QUIC` + `security` |
| 9002 | `QUIC` + `congestion control` |
| 9312 | `QUIC` + `network management` |
| 3261 | `SIP` |
| 2119 | `terminology` |
| 1149 | `humor` |
| 6762 | `mDNS`, `DNS` |
| 5317 | no `JWT` |

### Search grounding (R9)

For each topic, confirm the name is phrasing people search for, not a librarian's abstraction. Record the phrasing considered when a topic is added.

### Rule audits (R9)

- **Embedded words.** For every rule alternative that is a plain word or phrase without `\b`, find corpus matches inside longer words and confirm each is an intended stem.
- **Acronym case.** For every alternative written as an uppercase acronym, list matches whose actual text is not uppercase and confirm each is a lowercase author keyword rather than an English word.

### Working groups (R10, R11)

- **Absorption by working group.** For each working group mapped only to topics or to a parent technology, count its documents and the title mentions of the group's own name. Ten or more documents with no tag of their own is a missing technology.
- **Absorption by title.** Run `tag_candidates.py` and read `tag-candidates.json` from the top. Each entry is a name an RFC title introduces beside its expansion — "Kerberized Internet Negotiation of Keys (KINK)" — that a reader cannot reach by searching the tag the RFC was filed under. This is R11's evidence test run over the whole corpus, and it finds what the working-group count cannot: technologies that never had a group of their own. About half the entries are components, versions or names for the tag itself; the rest are candidates for promotion, checked against R10 (a following), R13 (a single document may suffice) and R14–R15 (not an organisation).
- **Names.** For every tag whose slug matches a working-group acronym, count RFCs whose title, keywords or abstract use the term other than as a reference to the group. Zero such uses means the tag is named for the group, not the technology, and must be renamed or removed.

### Overlap

List non-ancestor tag pairs with Jaccard similarity above 0.35 over their document sets. Confirm each reflects a real relationship, not a map entry assigning both.

### Root leaks (R12)

For each root, count the RFCs carrying it as a leaf tag beside a technology from another root, and read the titles. Correct co-occurrence looks like RFC 1812 (`IPv4`, `routing`) or RFC 5095 (`IPv6`, `routing`): the title is about the root's subject. A leak looks like RFC 3268 (`TLS`, `transport`): the root's rule matched a word inside a protocol name — Transport Layer Security, Real-Time Transport Protocol, Generic Routing Encapsulation, JSON Web Token. In the Overlap view of `rfc-tags.html` leaks show as a root nested inside an unrelated technology. The check has a second half: after tightening a root rule, list documents that carried the root before and no longer do, and read those titles too — RFC 3222 (FIB-based router performance) and RFC 6192 (the router control plane) are routing documents that a tightened `routing` rule once dropped. A document that loses its only tag falls to the abstract fallback and may pick up unrelated tags there. Leaks matter more than search noise: every one fires a notification to every subscriber of the root.

### Topic gaps (R8, R10)

List served-view documents whose only topics are roots but whose titles contain aspect words — manageability, operational, congestion, mobility, compression, discovery, authentication — and inspect for missing rules.

### Keyword noise (R20)

For each topic-implying technology, list assignments with no title evidence and confirm they are working-group-derived rather than incidental keywords.

### Id form (R21)

- Every id is in the allowed form and no two ids would be confused with each other after case-folding, normalisation and whitespace collapsing (the loader fails otherwise; see code.md, Identity of an id).
- Ids read exactly as the documents write the term (`IPv6`, `HTTP/2`, `.onion`, `X.509`, `TACACS+`); phrases are written with spaces and their own casing (`congestion control`, `IP mobility`).
- Paths are written as ids joined by ` / `.

### Independence (R14, R15)

By inspection of the tree: no tag names an IETF area, a status, a stream or a date.

### Engine round-trip

When the engine or the YAML schema changes, re-run against the previous `rfc-tags.json` and list every RFC whose `tags` differ. Differences must be explainable — at the YAML-to-engine migration nine RFCs differed, all in which tags survive the seven-tag cap or the three-tag abstract fallback, and none in tags matched.

## Records

- `alias-candidates.csv` — alias candidates extracted from an external taxonomy, with RFC usage counts, held for review against the alias criterion in README.md.

## Figures (current build)

### Curated tree

- **Tags:** 635 — 19 roots, 289 at level 2, 281 at level 3, 46 at level 4; 553 technology, 82 topic.
- **Coverage:** 0 untagged.
- **Tags per RFC (with ancestors):** mean 3.66, median 3, max 15.
- **Distribution:** 1:679 · 2:2,570 · 3:2,132 · 4:1,588 · 5:1,330 · 6:719 · 7:418 · 8:216 · 9:102 · 10:39 · 11:24 · 12:10 · 13:4 · 14:3 · 15:1.
- **Over ten tags:** 42 documents (0.4%), all multi-technology cross-area specifications.
- **Unused tags:** 0.
- **Single-document tags:** 44 — AFS, ARC, BATS, BLAKE2, CRC, CyberCash, DCTCP, Dragonfly, EIGRP, FFV1, GSAKMP, HOBA, HTTP caching, IDXP, IRTP, J-PAKE, JSCalendar, LPWAN, MOSPF, NAT-PMP, OPAQUE, OVSDB, PGM, RATP, RBNF, SDF, SFrame, Speex, TBRPF, TEEP, TMux, TVR, Tetrys, Vorbis, WHIP, XACML, Y2K, YAML, amateur radio, data center networking, eBPF, oblivious DNS, password hashing, scrypt.
- **Humor:** 74 documents, 0 exclusivity violations.
- **Stability replay:** 9,214 RFCs debut no tag, 609 debut one, 10 debut two, 2 debut three. The 12 multi-debut cases are parent-and-child pairs founding a branch, plus RFC 2430 preceding the MPLS architecture into print.

### Served view

- **Axes:** 553 technology tags, 76 topics.
- **Zero-technology documents:** 1,483 — governance, process, humor, ARPANET-era notes, general-subject documents.
- **Zero-topic documents:** 0.
- **Per RFC:** technology mean 1.74, topic mean 2.06, combined mean 3.80.
- **Over ten combined:** 48 documents (0.5%); maximum 15.
- **Documents whose only topics are roots:** 5,335.
- **Topic replay:** 5 documents debut two topics, all in the founding years. Debuts since 2003: emergency services (2003), NAT traversal (2003), IoT (2006), energy management (2013), SDN (2014), telemetry (2019), sustainability (2024).

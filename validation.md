# RFC Subject Tags — Validation

The checks a rebuild must pass, and the figures from the current build. Each check names the requirement in README.md it serves. The figures section is rewritten by `regen.py`.

## Checks

### Structural (R3, R5, R12)

`python3 engine.py` loads both normative files without error. It asserts:

- every id unique, and every `parent`, `implies` and `decomposes_to` reference resolves;
- depth at most four levels;
- every root is a topic;
- no catch-all names.

### Coverage (R7, R8)

- No RFC without a tag.
- In the served view, no RFC without a topic.

### Budget (R4, R6)

- Every assignment is emitted as full paths.
- Mean tags per RFC, counting ancestors, is between 1 and 10.
- Report the distribution and the maximum. There is no cap on tags: nothing trims the model's list.

### Humor (R16)

Both directions:

- every `humor` document carries nothing else (the tagger gives a review reason to any that does; nothing corrects it);
- every day-dated document carries `humor`. This is the model's judgement now, so list the day-dated documents that lack it and read them.

### Unused and single-document tags (R9, R13)

- No tag is carried by zero documents, counting documents beneath it — such a tag either has a description the model does not recognise documents by, or should not exist. A family tag whose every document also names a member (`hash-based signatures`, whose documents all name HSS/LMS, XMSS or SLH-DSA) has no leaf carriers yet is reached by all of them through closure; that is used.
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

### Working groups (R10, R11)

- **Absorption by working group.** For each working group whose documents mostly carry only topics or a parent technology, count its documents and the title mentions of the group's own name. Ten or more documents with no tag of their own is a missing technology.
- **Absorption by title.** Run `tag_candidates.py` and read `tag-candidates.json` from the top. Each entry is a name an RFC title introduces beside its expansion — "Kerberized Internet Negotiation of Keys (KINK)" — that a reader cannot reach by searching the tag the RFC was filed under. This is R11's evidence test run over the whole corpus, and it finds what the working-group count cannot: technologies that never had a group of their own. About half the entries are components, versions or names for the tag itself; the rest are candidates for promotion, checked against R10 (a following), R13 (a single document may suffice) and R14–R15 (not an organisation).
- **Names.** For every tag whose slug matches a working-group acronym, count RFCs whose title, keywords or abstract use the term other than as a reference to the group. Zero such uses means the tag is named for the group, not the technology, and must be renamed or removed.

### Overlap

List non-ancestor tag pairs with Jaccard similarity above 0.35 over their document sets. Confirm each reflects a real relationship, not a map entry assigning both.

### Review queue

Count the documents with a non-empty `review` in `rfc-tags.json`, by reason (the page's Review tab shows the same). A reason disappears when the document is tagged again and the cause is gone, or when the document gains an entry in `assignments.yaml`.

### Obsoleted-by agreement

A document and the RFC that obsoletes it are almost always about the same thing. List the pairs whose closed tag sets share nothing (the tagger adds a review reason to both sides). Read each: a tag that changed name across the generations (`hostnames` → `DNS`, `email` → `SMTP`) is fine; the same subject under unrelated tags is an error on one side. RFC 1766 (`SMTP`, from its working group) against RFC 3066 (`language tags`) was found this way.

### Overrides (assignments.yaml)

- The loader accepts the file: every RFC id well-formed, every tag named exists, every entry has a reason.
- No tag is carried *only* by overrides. Check that every tag added by an override is also chosen by the model for some document.
- The stability replay includes overridden documents; an override that debuts a tag is a new tag entering by hand and should be as rare as any other debut.
- The file is currently empty: the 48 entries that corrected the former rule engine were removed with it.

### Root leaks (R12)

For each root, count the RFCs carrying it directly beside a technology from another root, and read the model's reason for the root. Correct co-occurrence looks like RFC 1812 (`IPv4`, `routing`): the document is about the root's subject. A leak is a root chosen because its word appears inside a protocol name — Transport Layer Security, Generic Routing Encapsulation, JSON Web Token. The instructions tell the model not to do this; the check is that it has not.

### Topic gaps (R8, R10)

List served-view documents whose only topics are roots but whose titles contain aspect words — manageability, operational, congestion, mobility, compression, discovery, authentication — and inspect for a missing topic. The `gaps` each entry of `rfc-tags.json` records are the model's own list of subjects it found no tag for; read them by frequency.

### Substrate noise (R20)

For each topic-implying technology, sample assignments where the model gave it the `secondary` role and confirm the document is about the technology and does not merely run over it.

### Id form (R21)

- Every id is in the allowed form and no two ids would be confused with each other after case-folding, normalisation and whitespace collapsing (the loader fails otherwise; see code.md, Identity of an id).
- Ids read exactly as the documents write the term (`IPv6`, `HTTP/2`, `.onion`, `X.509`, `TACACS+`); phrases are written with spaces and their own casing (`congestion control`, `IP mobility`).
- Paths are written as ids joined by ` / `.

### Identity (uuid and slug)

- Every tag has a version-4 `uuid`, no two the same (the loader fails otherwise).
- Every `slug` equals Django `slugify` of its id with each `+` written as `p`, deduplicated in file order (the loader fails otherwise).
- Renames preserve uuids: after any rename, diff the set of uuids against the previous build — it must be unchanged.

### Independence (R14, R15)

By inspection of the tree: no tag names an IETF area, a status, a stream or a date.

### Round-trip

`rfc-tags.json` is tracked, so `git diff` shows every RFC whose assignment a change moves. After a change to `engine.py`, `tagger.py` or the YAML schema, run `tagger.py --no-model` and read the diff: differences must be explainable. After a `--retag`, the diff is the review. (History: at the YAML-to-engine migration nine RFCs differed, all in the three-tag abstract fallback's choice or the leaf cap that then existed, and none in tags matched.)

## Records

- `alias-candidates.csv` — alias candidates extracted from an external taxonomy, with RFC usage counts, held for review against the alias criterion in README.md.

## Figures (current build)

### Curated tree

- **Tags:** 638 — 19 roots, 290 at level 2, 280 at level 3, 49 at level 4; 556 technology, 82 topic.
- **Coverage:** 52 untagged, of which 7 the model has not read (no text in the corpus, or awaiting a tagger run).
- **Tags per RFC (with ancestors):** mean 3.68, median 3, max 24.
- **Distribution:** 0:52 · 1:371 · 2:2,211 · 3:2,787 · 4:1,698 · 5:1,407 · 6:703 · 7:342 · 8:155 · 9:73 · 10:21 · 11:22 · 12:5 · 13:7 · 14:4 · 15:1 · 16:4 · 17:3 · 18:1 · 21:1 · 24:1.
- **Over ten tags:** 49 documents (0.5%).
- **Unused tags (no document directly or beneath):** 0.
- **Single-document tags:** 39 — AEGIS, AODV, ARC, BATS, BLAKE2, CyberCash, DSR, EIGRP, FFV1, GSM, HEVC, HOBA, HSRP, HSTS, IRTP, J-PAKE, JSCalendar, JSONPath, LPWAN, LoRaWAN, OPAQUE, OVSDB, PGM, RBNF, SDF, Sigfox, Speex, TBRPF, TEEP, TMux, Tetrys, VP9, Vorbis, WHIP, WebAuthn, XACML, YAML, eBPF, hash-based signatures.
- **Humor:** 78 documents, 42 carrying other tags as well (R16).
- **Stability replay:** 9,264 RFCs debut no tag, 577 debut one, 25 debut two, 2 debut three. 28 documents debut more than one tag.

### Served view

- **Axes:** 556 technology tags, 76 topics.
- **Zero-technology documents:** 1,182 — governance, process, humor, ARPANET-era notes, general-subject documents.
- **Zero-topic documents:** 52.
- **Per RFC:** technology mean 1.81, topic mean 2.03, combined mean 3.84.
- **Over ten combined:** 56 documents (0.6%); maximum 25.
- **Documents whose only topics are roots:** 5,268.
- **Topic replay:** 7 documents debut two or more topics. Debuts since 2003: emergency services (2003), NAT traversal (2003), IoT (2005), intrusion detection (2007), energy management (2012), SDN (2014), autonomic networking (2015), telemetry (2016), sustainability (2022).

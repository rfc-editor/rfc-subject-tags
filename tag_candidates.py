#!/usr/bin/env python3
"""Harvest candidate tags from RFC titles.

RFC titles spell out a name and its acronym on first use -- "Simple Network Time
Protocol (SNTP)", "Kerberized Internet Negotiation of Keys (KINK)". When such a
name is not reachable by searching the tag its RFC was filed under, the RFC is
naming a technology the vocabulary has absorbed into something broader. R10 says
a technology with a following gets its own tag; R11 says the evidence is an RFC
using the name as the name of the thing -- which is exactly what a title does.

    python3 tag_candidates.py                       # whole corpus
    python3 tag_candidates.py --since 2025          # recent RFCs only
    python3 tag_candidates.py --min-rfcs 2

This calls no model and costs nothing, so it runs on every build and its output
is published beside the assignments. It generates candidates; it does not judge
them. Roughly half of what it finds is not a missing tag -- a component (LSP under
mpls), a version (IKEv2 under ike), or a name for the tag itself. A curator reads
from the top, where the counts are highest, and decides.

Derived from the alias harvester on the alias-candidates branch by R. Sparks;
reframed here for the tag vocabulary.

Reads, all of which the build already has on disk at this point:
    taxonomy.yaml   for ids, descriptions and match rules
    rfcs.json       for titles
    rfc-tags.json   for the tags each RFC was assigned
"""
import argparse, json, re, sys
from collections import defaultdict

import yaml

# "Some Expanded Name (ACRO)" -- the expansion is what tells us which tag the
# acronym belongs to.
TITLE_ACRONYM = re.compile(r'([A-Za-z][A-Za-z0-9 ,/-]{4,70}?)\s*\(([A-Za-z][A-Za-z0-9./+-]{1,14})\)')

WORD = re.compile(r'[^a-z0-9.+#/]+')
SUBWORD = re.compile(r'[^a-z0-9]+')
words = lambda s: [x for x in WORD.split(str(s or '').lower()) if x]
subwords = lambda s: [x for x in SUBWORD.split(str(s or '').lower()) if x]


def load(taxonomy_path):
    tags = yaml.safe_load(open(taxonomy_path))["tags"]
    by_id = {t["id"]: t for t in tags}
    match = {t: [re.compile(p, re.I) for p in e.get("match", []) + e.get("match_title_only", [])]
             for t, e in by_id.items()}

    def depth(tid):
        d, seen = 0, set()
        while tid and tid not in seen:
            seen.add(tid); d += 1; tid = by_id[tid].get("parent")
        return d

    return by_id, match, {t: depth(t) for t in by_id}


def reachable(entry, term):
    """Would typing `term` into the tag search already land on this tag?
    Mirrors scoreTag() in browser_template.html: exact or prefix match on the id,
    on the id's hyphen-separated parts, or on a whole word of the description."""
    q = term.lower()
    tid = entry["id"].lower()
    if tid == q or tid.startswith(q):
        return True
    if any(k == q or k.startswith(q) for k in subwords(entry["id"])):
        return True
    if any(k == q or k.startswith(q) for k in words(entry.get("desc", ""))):
        return True
    return False


def harvest(recs, assigned, by_id, match, depth, since=None):
    found = defaultdict(lambda: defaultdict(list))
    for r in recs:
        year = r.get("year")
        if since and (not str(year).isdigit() or int(year) < since):
            continue
        title = r.get("title") or ""
        tags = assigned.get(r["id"], {}).get("tags", [])
        if not tags:
            continue
        for m in TITLE_ACRONYM.finditer(title):
            expansion, acronym = m.group(1), m.group(2)
            if sum(c.isupper() for c in acronym) < 2:
                continue
            # Attribute to the most specific tag whose own rules fire on the
            # expansion; if the acronym is already reachable there, the tag
            # exists and nothing is proposed.
            hits = [t for t in tags if any(rx.search(expansion) for rx in match[t])]
            if not hits:
                continue
            best = max(hits, key=lambda t: depth[t])
            if reachable(by_id[best], acronym):
                continue
            found[best][acronym].append(r["id"])
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--taxonomy", default="taxonomy.yaml")
    p.add_argument("--corpus", default="rfcs.json")
    p.add_argument("--assignments", default="rfc-tags.json")
    p.add_argument("--since", type=int, help="only RFCs published in this year or later")
    p.add_argument("--out", default="tag-candidates.json")
    p.add_argument("--min-rfcs", type=int, default=1, help="drop candidates seen in fewer RFCs")
    args = p.parse_args()

    by_id, match, depth = load(args.taxonomy)
    recs = json.load(open(args.corpus))
    assigned = json.load(open(args.assignments))
    found = harvest(recs, assigned, by_id, match, depth, args.since)

    out = {
        "generated_from": {"rfcs": len(recs), "tags": len(by_id), "since": args.since},
        "note": ("Candidates only. Each is a name an RFC title introduces beside its expansion "
                 "that no reader can reach by searching the tag the RFC was filed under. "
                 "Roughly half are components, versions or names for the tag itself; the rest "
                 "are technologies the vocabulary may have absorbed (R10)."),
        "candidates": [],
    }
    for tid in sorted(found):
        for acronym, rfcs in sorted(found[tid].items(), key=lambda kv: -len(kv[1])):
            if len(rfcs) < args.min_rfcs:
                continue
            out["candidates"].append({"tag": tid, "term": acronym, "rfcs": len(rfcs),
                                      "examples": sorted(rfcs)[:5], "desc": by_id[tid].get("desc", "")})
    out["candidates"].sort(key=lambda c: (-c["rfcs"], c["tag"], c["term"]))
    out["generated_from"]["candidates"] = len(out["candidates"])
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(f"{len(out['candidates'])} candidates across {len(found)} tags -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

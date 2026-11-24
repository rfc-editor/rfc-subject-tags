#!/usr/bin/env python3
"""RFC subject tag taxonomy: loads and validates taxonomy.yaml and assignments.yaml, and derives the
paths and the two-axis (technology / topic) view from a list of tags.

Usage:  python3 engine.py [taxonomy.yaml] [assignments.yaml]     validate both files and report
Tags are assigned by tagger.py, which uses this module; this file knows nothing about how a tag is chosen.
"""
import json, re, sys, collections, unicodedata, uuid
import yaml

# What an id may look like. Ids are written as the documents write the term, so they may
# contain spaces and the punctuation those terms use; the character set is otherwise closed
# so that the formats built on ids stay unambiguous:
#   ' / ' joins a path        (rfc-tags.csv, the page)      -> ' / ' may not occur in an id
#   ';'  separates list items (rfc-tags.csv)                -> ';' and '|' are not allowed
#   ids are inserted into HTML attributes and text          -> no '"', '<', '>', '&' (and the page escapes anyway)
#   lookalikes                                              -> ASCII only, single spaces, none leading or trailing
ID_RE = re.compile(r'[A-Za-z0-9.][A-Za-z0-9._/+-]*(?: [A-Za-z0-9._/+-]+)*')

def id_key(s):
    """The identity of an id for uniqueness and for matching user input: case-folded, NFC,
    whitespace collapsed. Every lookup the engine does on stored data is exact; this is for
    deciding that two spellings would be the *same* id."""
    return ' '.join(unicodedata.normalize('NFC', s).casefold().split())

UUID4_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')

def slugify(value, allow_unicode=False):
    """Django's slugify, copied verbatim (django.utils.text.slugify).

    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated dashes to
    single dashes. Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace, dashes, and
    underscores."""
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")

def slugs_for(ids):
    """Slug for every id, in order. Before slugifying, each "+" becomes "p" (WHOIS++ -> whoispp,
    TACACS+ -> tacacsp, as the language name C++ is conventionally written cpp), since Django's
    algorithm would otherwise drop plus signs and lose the distinction the name carries. Any slug
    that would still repeat an earlier one gets -2, -3, ..."""
    seen = collections.Counter(); out = {}
    for i in ids:
        base = slugify(i.replace('+', 'p')) or 'tag'
        seen[base] += 1
        out[i] = base if seen[base] == 1 else f'{base}-{seen[base]}'
    return out

MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

class Taxonomy:
    def __init__(self, path='taxonomy.yaml', require_ids=True):
        """require_ids=False lets regen.py load a file whose tags lack uuid/slug in order to assign them."""
        self.require_ids = require_ids
        doc = yaml.safe_load(open(path))
        self.tags = doc['tags']                      # list, in file order
        self.by_id = {t['id']: t for t in self.tags}
        self.order = [t['id'] for t in self.tags]
        self._validate()
        self.path = {t: self._path(t) for t in self.by_id}
        self.root = {t: p[0] for t, p in self.path.items()}
        self.kind = {t: self.by_id[t]['kind'] for t in self.by_id}
        self.desc = {t: self.by_id[t]['desc'] for t in self.by_id}
        self.uuid = {t: self.by_id[t].get('uuid') for t in self.by_id}
        self.slug = {t: self.by_id[t].get('slug') for t in self.by_id}
        self.by_uuid = {u: t for t, u in self.uuid.items()}
        self.by_slug = {sl: t for t, sl in self.slug.items()}
        self.implies = {t: list(e.get('implies', [])) for t, e in self.by_id.items() if e.get('implies')}
        self.decomp = {t: list(e.get('decomposes_to', [])) for t, e in self.by_id.items() if e.get('decomposes_to')}

    def lookup(self, text):
        """Resolve user input to an id, ignoring case and spacing; None if there is no such tag.
        This is the one place case-insensitive matching happens: stored references (parent,
        implies, decomposes_to, rfc-tags.json) are exact."""
        return self.by_key.get(id_key(text))

    def _path(self, t):
        p = [t]
        while 'parent' in self.by_id[p[-1]]: p.append(self.by_id[p[-1]]['parent'])
        return tuple(reversed(p))

    def _validate(self):
        ids = [t['id'] for t in self.tags]
        for i in ids:
            assert ID_RE.fullmatch(i), (f'id {i!r} is not allowed: ids use letters, digits, space and . _ / + - only, '
                                        'single spaces, none leading or trailing')
            assert ' / ' not in i, f'id {i!r} contains the path separator " / "'
        dup = [k for k, c in collections.Counter(id_key(i) for i in ids).items() if c > 1]
        assert not dup, f'ids that would be confused with each other (same ignoring case and spacing): {dup}'
        self.by_key = {id_key(t['id']): t['id'] for t in self.tags}
        for e in self.tags:
            assert e['kind'] in ('technology', 'topic'), e['id']
            assert not any(b in e['id'].lower() for b in ('misc', 'other', 'general')), f'catch-all name: {e["id"]}'
            if 'parent' in e: assert e['parent'] in self.by_id, f'{e["id"]}: unknown parent {e["parent"]}'
            else: assert e['kind'] == 'topic', f'root {e["id"]} must be a topic'
            for f in ('implies', 'decomposes_to'):
                for x in e.get(f, []): assert x in self.by_id, f'{e["id"]}.{f}: unknown tag {x}'
        for t in self.by_id:
            assert len(self._path(t)) <= 4, f'too deep: {t}'
        if not self.require_ids:
            return
        # uuid: assigned once by regen.py and never changed -- an id may be renamed, its uuid may not
        us = [e.get('uuid') for e in self.tags]
        for e, u in zip(self.tags, us):
            assert u, f"{e['id']}: no uuid (run regen.py, which assigns one to any tag lacking it)"
            assert UUID4_RE.fullmatch(str(u)), f"{e['id']}: uuid {u!r} is not a version-4 UUID"
        dupu = [u for u, c in collections.Counter(us).items() if c > 1]
        assert not dupu, f'uuid shared by more than one tag: {dupu}'
        # slug: Django slugify of the id, deduplicated in file order; regen.py regenerates it every run
        expected = slugs_for(ids)
        for e in self.tags:
            assert e.get('slug') == expected[e['id']], (f"{e['id']}: slug {e.get('slug')!r} should be {expected[e['id']]!r} "
                                                        "(slugs are generated from the id; run regen.py)")

    # ---- overrides ----------------------------------------------------------
    def load_overrides(self, path='assignments.yaml'):
        """Hand assignments, applied after the model's. Each entry names an RFC and the tags to add or
        remove, with a reason. A document with an entry has been reviewed by a person."""
        try:
            doc = yaml.safe_load(open(path)) or {}
        except FileNotFoundError:
            doc = {}
        self.overrides = {}
        for rid, o in (doc.get('overrides') or {}).items():
            assert re.fullmatch(r'RFC\d+', rid), f'assignments.yaml: {rid!r} is not an RFC id'
            o = o or {}
            for f in ('add', 'remove'):
                for t in o.get(f, []) or []:
                    assert t in self.by_id, f'assignments.yaml: {rid} {f}s unknown tag {t!r}'
            assert o.get('reason'), f'assignments.yaml: {rid} needs a reason'
            self.overrides[rid] = o
        return self.overrides

    def closure(self, tags):
        out = set()
        for t in tags: out.update(self.path[t])
        return out

    # ---- served view ------------------------------------------------------
    def two_axis(self, tags):
        tech, topic = set(), set()
        for t in self.closure(tags):
            if t in self.decomp:
                topic.update(self.decomp[t]); continue
            if self.kind[t] == 'topic':
                topic.add(t)                          # a topic may imply another (cryptography -> security)
            else:
                tech.add(t)
            topic.update(self.implies.get(t, []))
        return sorted(tech), sorted(topic)

def load_rfcs(path='rfcs.json'):
    return json.load(open(path))

if __name__ == '__main__':
    tax = Taxonomy(sys.argv[1] if len(sys.argv) > 1 else 'taxonomy.yaml')
    ov = tax.load_overrides(sys.argv[2] if len(sys.argv) > 2 else 'assignments.yaml')
    print(f"{len(tax.by_id)} tags ({dict(collections.Counter(tax.kind.values()))}); {len(ov)} hand assignments; both files are valid")

#!/usr/bin/env python3
"""RFC subject tag engine: reads taxonomy.yaml, assigns tags to RFC records, derives the two-axis view.

Usage:  python3 engine.py [taxonomy.yaml] [rfcs.json]
Writes  rfc-tags.json: for every RFC its leaf tags, full paths, and technology/topic coordinates.
All per-tag knowledge lives in the YAML; this file is the algorithm only.
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
        self.engine = doc['engine']
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
        flags = re.I
        self.match = {t: [re.compile(p, flags) for p in e.get('match', [])] for t, e in self.by_id.items()}
        self.match_title = {t: [re.compile(p, flags) for p in e.get('match_title_only', [])] for t, e in self.by_id.items()}
        self.streams = collections.defaultdict(list)
        for t, e in self.by_id.items():
            for st in e.get('streams', []): self.streams[st].append(t)
        self.groups = collections.defaultdict(list)
        for t, e in self.by_id.items():
            for g in e.get('groups', []): self.groups[g].append(t)
        self.yields = {t: set(e.get('yields_to', [])) for t, e in self.by_id.items() if e.get('yields_to')}
        self.implies = {t: list(e.get('implies', [])) for t, e in self.by_id.items() if e.get('implies')}
        self.decomp = {t: list(e.get('decomposes_to', [])) for t, e in self.by_id.items() if e.get('decomposes_to')}
        self.max_year = {t: e['max_year'] for t, e in self.by_id.items() if 'max_year' in e}

    def lookup(self, text):
        """Resolve user input to an id, ignoring case and spacing; None if there is no such tag.
        This is the one place case-insensitive matching happens: stored references (parent,
        implies, yields_to, decomposes_to, rfc-tags.json) are exact."""
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
            for f in ('yields_to', 'implies', 'decomposes_to'):
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

    # ---- assignment -------------------------------------------------------
    # ---- overrides ----------------------------------------------------------
    def load_overrides(self, path='assignments.yaml'):
        """Hand assignments, applied after the rules. Each entry names an RFC and the tags to add or
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

    # ---- assignment -------------------------------------------------------
    EVIDENCE_ORDER = ['override', 'wg', 'stream', 'title', 'keyword', 'abstract', 'era']

    def assign(self, rfc):
        """Leaf tags for one RFC. Also sets self.last_evidence ({tag: [sources]}), self.last_source
        and self.last_review (reasons a person should look at the assignment; empty if none)."""
        E = self.engine; hum = E['humor']['tag']
        ov = getattr(self, 'overrides', {}).get(rfc['id'], {})
        if rfc.get('day') or rfc['id'] in self.by_id[hum].get('documents', []):
            self.last_evidence = {hum: ['title']}; self.last_source = 'rules'; self.last_review = []
            return [hum]
        tags = []; ev = collections.defaultdict(list)
        year = rfc.get('year') or 0
        def add(ts, src):
            for t in ts:
                if t in self.max_year and year > self.max_year[t]: continue
                if t not in tags: tags.append(t)
                if src not in ev[t]: ev[t].append(src)
        wg = rfc.get('wg')
        wg_tags = set(self.groups.get(wg, [])) if wg else set()
        add(wg_tags, 'wg')
        add(self.streams.get(rfc.get('stream'), []), 'stream')   # a publication stream is evidence too: Editorial -> RFC series
        title = rfc.get('title') or ''
        kws = ' ; '.join(rfc.get('keywords') or '')
        for t in self.order:
            if any(rx.search(title) for rx in self.match[t]): add([t], 'title')
            elif kws and any(rx.search(title + ' ; ' + kws) for rx in self.match[t]): add([t], 'keyword')
        for t in self.order:
            if any(rx.search(title) for rx in self.match_title[t]): add([t], 'title')
        self.last_source = 'rules'
        if not tags and not ov.get('add'):
            self.last_source = 'abstract'
            abstract = rfc.get('abstract') or ''
            hits = [t for t in self.order if any(rx.search(abstract) for rx in self.match[t])]
            add(self._prioritise(hits, wg_tags)[:E['abstract_fallback_max_tags']], 'abstract')
        era = E['era_fallback']
        if not tags and not ov.get('add') and rfc.get('year') and rfc['year'] <= era['max_year'] and rfc.get('stream') == era['stream']:
            add([era['tag']], 'era'); self.last_source = 'era'
        tags = self._suppress(tags)
        tags = [t for t in tags if not any(o != t and t in self.path[o] for o in tags)]   # ancestor rule
        implied = {x for o in tags for x in self.implies.get(o, [])}
        tags = [t for t in tags if t not in implied]                                      # implied topics are not leaves
        before_cap = len(tags)
        tags = self._prioritise(tags, wg_tags)[:E['max_leaf_tags']]
        # overrides: applied last, not subject to the cap
        for t in ov.get('remove', []) or []:
            if t in tags: tags.remove(t)
        for t in ov.get('add', []) or []:
            if t not in tags: tags.append(t)
            ev[t] = ['override'] + [x for x in ev.get(t, []) if x != 'override']
        tags = [t for t in tags if not any(o != t and t in self.path[o] for o in tags)]
        self.last_evidence = {t: sorted(ev.get(t, []), key=self.EVIDENCE_ORDER.index) for t in tags}
        self.last_review = [] if ov else self._review(rfc, tags, before_cap)
        return tags

    def _review(self, rfc, tags, before_cap):
        """Why a person should look at this assignment. Each reason is one of the failure modes the
        pipeline is known to have; a document with none is not thereby right, only unremarkable."""
        r = []
        if self.last_source == 'abstract': r.append('no match: tags come from the abstract')
        if self.last_source == 'era': r.append('no match: era fallback')
        for t in tags:
            src = self.last_evidence.get(t, [])
            if self.kind[t] == 'technology' and src and set(src) <= {'keyword'}:
                r.append(f'{t}: technology on author keywords alone')
        if before_cap > self.engine['max_leaf_tags']:
            r.append(f'{before_cap} tags matched; {before_cap - self.engine["max_leaf_tags"]} dropped by the cap')
        # a root as leaf beside a technology from another subtree, when the root came from a title word
        # rather than a working group or stream: the pattern behind the transport/routing leaks
        for rt in [t for t in tags if len(self.path[t]) == 1]:
            if set(self.last_evidence.get(rt, [])) & {'wg', 'stream'}: continue
            foreign = [t for t in tags if self.kind[t] == 'technology' and self.root[t] != rt]
            if foreign: r.append(f'{rt} as leaf beside {", ".join(foreign)}')
        return r

    def _suppress(self, tags):
        """Remove generic tags that yield to a present specific. A specific counts only once it is
        settled - it has no yields_to of its own, or none of its own specifics are present - so that a
        keyword-noise tag removed by suppression cannot itself suppress something else."""
        present = list(tags)
        def settled(s): return s not in self.yields or not (self.yields[s] & set(present))
        changed = True
        while changed:
            changed = False
            for t in list(present):
                if t in self.yields and any(s in present and settled(s) for s in self.yields[t]):
                    present.remove(t); changed = True
        for t in list(present):                                  # any cycle left over: plain rule
            if t in self.yields and self.yields[t] & set(present): present.remove(t)
        return present

    def _prioritise(self, tags, wg_tags=()):
        """Order used when limits truncate: working-group tags first, then deeper (more specific) tags, then file order."""
        pos = {t: i for i, t in enumerate(self.order)}
        return sorted(tags, key=lambda t: (t not in wg_tags, -len(self.path[t]), pos[t]))

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
    tax.load_overrides(sys.argv[3] if len(sys.argv) > 3 else 'assignments.yaml')
    rfcs = load_rfcs(sys.argv[2] if len(sys.argv) > 2 else 'rfcs.json')
    out = {}
    for r in rfcs:
        leaf = tax.assign(r)
        tech, topic = tax.two_axis(leaf)
        out[r['id']] = {'title': r.get('title'), 'year': r.get('year'), 'tags': leaf, 'source': tax.last_source,
                        'evidence': tax.last_evidence, 'review': tax.last_review, 'reviewed': r['id'] in tax.overrides,
                        'paths': [list(p) for p in sorted({tax.path[t][:i] for t in leaf for i in range(1, len(tax.path[t]) + 1)})],
                        'technology': tech, 'topic': topic}
    # a tag's first document, in publication order, is worth a look: it is where a new tag or a
    # misfiring rule shows up first (R18)
    MON = {m: i for i, m in enumerate(MONTHS, 1)}
    seen = set()
    for r in sorted(rfcs, key=lambda r: (r.get('year') or 0, MON.get(r.get('month'), 6), int(r['id'][3:]))):
        k = r['id']; new = [t for t in out[k]['tags'] if t not in seen]; seen.update(new)
        if new and not out[k]['reviewed'] and (r.get('year') or 0) >= 2000:
            out[k]['review'].append('first document to carry ' + ', '.join(new))
    # a document and the one that obsoletes it are almost always about the same thing: no tag in
    # common, counting ancestors, means one of the two assignments is probably wrong
    closed = {k: {t for p in v['paths'] for t in p} for k, v in out.items()}
    for r in rfcs:
        for o in r.get('obsoleted_by') or []:
            if o in out and closed[r['id']] and closed[o] and not (closed[r['id']] & closed[o]):
                if not out[r['id']]['reviewed']: out[r['id']]['review'].append(f'no tag in common with {o}, which obsoletes it')
                if not out[o]['reviewed']: out[o]['review'].append(f'no tag in common with {r["id"]}, which it obsoletes')
    json.dump(out, open('rfc-tags.json', 'w'), indent=1)
    used = collections.Counter(t for v in out.values() for t in v['tags'])
    carried = collections.Counter(t for v in out.values() for p in v['paths'] for t in p)   # directly or beneath
    print(f"{len(tax.by_id)} tags ({dict(collections.Counter(tax.kind.values()))}); untagged {sum(1 for v in out.values() if not v['tags'])}; "
          f"unused {[t for t in tax.by_id if t not in carried]}; zero-topic {sum(1 for v in out.values() if not v['topic'])}; "
          f"needing review {sum(1 for v in out.values() if v['review'])}; overridden {sum(1 for v in out.values() if v['reviewed'])}")

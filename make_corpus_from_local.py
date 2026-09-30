#!/usr/bin/env python3
"""Build rfcs.json from a local corpus directory, one .json metadata file per RFC.

The engine (engine.py) consumes a list of records with these fields:
  id (e.g. "RFC9000"), title, year (int), month (name), day (int or None),
  keywords (list), abstract (str), wg (working group acronym or None),
  stream, status  -- stream/status are informational only.

Written against the RFC Editor's per-RFC JSON (rfc-editor.org/rfc/rfcNNNN.json):
doc_id, title, abstract, keywords, pub_date ("May 2021"), status, source (the
working group's *name*), obsoletes/obsoleted_by/updates/updated_by. That schema
has no stream field and gives no day of month; both come from the index. Adjust the FIELD_MAP below to match —
each entry maps a field name used here to a list of candidate keys tried in order.

Usage:  python3 make_corpus_from_local.py ~/Data/RFCs rfcs.json

Local metadata files may lack fields the engine relies on: the publication stream
(the era fallback and the Editorial-stream rule need it), the day of month for the
April 1st series, and the working-group acronym (some layouts hold the group's name
instead). When rfc-index.xml is present alongside, or can be downloaded, those fields
are filled from it for every RFC it knows. "Not Issued" placeholder records are
dropped.
"""
import json, pathlib, re, sys

FIELD_MAP = {
    'title':    ['title'],
    'abstract': ['abstract'],
    'keywords': ['keywords', 'keyword'],
    'wg':       ['source', 'wg', 'group'],          # some layouts put the group in "source"
    'status':   ['status', 'current_status'],
    'stream':   ['stream'],
    'date':     ['date', 'pub_date', 'published'],  # expects e.g. "April 2021" or "1 April 2021"
}
MONTHS = ['January','February','March','April','May','June','July','August',
          'September','October','November','December']

def pick(d, keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ''):
            return d[k]
    return default

def parse_date(s):
    """Return (year, month_name, day_or_None) from strings like 'April 2021' / '1 April 1998'."""
    if isinstance(s, dict):  # some schemas: {"month": "April", "year": 2021, "day": 1}
        return s.get('year'), s.get('month'), s.get('day')
    year = month = day = None
    if s:
        m = re.search(r'(\d{4})', s)
        year = int(m.group(1)) if m else None
        for mo in MONTHS:
            if mo.lower() in s.lower():
                month = mo
                break
        m = re.match(r'\s*(\d{1,2})\s+[A-Za-z]', s)
        day = int(m.group(1)) if m else None
    return year, month, day

def index_fields(path='rfc-index.xml'):
    """{id: {stream, day, wg}} from the RFC Editor index, downloading it if absent."""
    try:
        import make_corpus_from_index as mci, xml.etree.ElementTree as ET, urllib.request, os
        if not os.path.exists(path):
            urllib.request.urlretrieve('https://www.rfc-editor.org/rfc-index.xml', path)
        root = ET.parse(path).getroot(); out = {}
        for e in root.findall('r:rfc-entry', mci.NS):
            date = e.find('r:date', mci.NS)
            out[mci.text(e, 'doc-id')] = {'stream': mci.text(e, 'stream'),
                                          'day': int(mci.text(date, 'day')) if date is not None and mci.text(date, 'day') else None,
                                          'wg': (mci.text(e, 'wg_acronym') or '').lower() or None}
        return out
    except Exception as ex:  # no network, no index: proceed with what the local files have
        print(f'index not available ({ex}); stream/day/wg not filled', file=sys.stderr); return {}

def main(src_dir, out_path):
    idx = index_fields()
    out = []
    for p in sorted(pathlib.Path(src_dir).glob('rfc*.json')):
        num = re.search(r'rfc(\d+)', p.name, re.I)
        if not num:
            continue
        meta = json.loads(p.read_text(errors='replace'))
        year, month, day = parse_date(pick(meta, FIELD_MAP['date']))
        kw = pick(meta, FIELD_MAP['keywords'], [])
        if isinstance(kw, str):
            kw = [k.strip() for k in re.split(r'[;,]', kw) if k.strip()]
        rid = f'RFC{int(num.group(1))}'
        title = pick(meta, FIELD_MAP['title'], '')
        if title.strip() == 'Not Issued' or not year:
            continue                                   # placeholder for a number never published
        wg = pick(meta, FIELD_MAP['wg'])
        if wg and wg.upper() in ('NON WORKING GROUP', 'INDEPENDENT', 'LEGACY', 'IETF - NON WORKING GROUP'):
            wg = None
        ix = idx.get(rid) or {}
        if ix.get('wg') and (not wg or ' ' in wg):    # local files hold the group's name; the engine keys on the acronym
            wg = ix['wg']
        if day is None and ix.get('day'):
            day = ix['day']
        out.append({
            'id': rid,
            'title': title,
            'abstract': pick(meta, FIELD_MAP['abstract'], '') or '',
            'keywords': kw,
            'wg': wg.lower() if wg else None,
            'status': pick(meta, FIELD_MAP['status']),
            'stream': pick(meta, FIELD_MAP['stream'], '') or (idx.get(rid) or {}).get('stream', ''),
            'year': year, 'month': month, 'day': day,
            # the relations the obsoleted-by review check needs (present in the RFC Editor's per-RFC JSON)
            'obsoletes': meta.get('obsoletes') or [], 'obsoleted_by': meta.get('obsoleted_by') or [],
            'updates': meta.get('updates') or [], 'updated_by': meta.get('updated_by') or [],
        })
    # fields the engine depends on: say so if they could not be filled
    no_stream = sum(1 for r in out if not r['stream'])
    if no_stream:
        print(f'warning: {no_stream} records have no stream; the era fallback and stream rules will not fire for them', file=sys.stderr)
    named = sum(1 for r in out if r['wg'] and ' ' in r['wg'])
    if named:
        print(f'warning: {named} records carry a working-group name rather than an acronym; the working-group map will not match them', file=sys.stderr)
    json.dump(out, open(out_path, 'w'))
    print(f'wrote {len(out)} records to {out_path}')

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path.home() / 'Data/RFCs')
    dst = sys.argv[2] if len(sys.argv) > 2 else 'rfcs.json'
    main(src, dst)

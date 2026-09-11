#!/usr/bin/env python3
"""Build rfcs.json from a local corpus directory, one .json metadata file per RFC.

The engine (engine.py) consumes a list of records with these fields:
  id (e.g. "RFC9000"), title, year (int), month (name), day (int or None),
  keywords (list), abstract (str), wg (working group acronym or None),
  stream, status  -- stream/status are informational only.

This adapter was written against the rfc-editor index schema. Per-RFC .json
files from other sources may name fields differently (the producing group, for
instance, is sometimes under "source"). Adjust the FIELD_MAP below to match —
each entry maps a field name used here to a list of candidate keys tried in order.

Usage:  python3 make_corpus_from_local.py ~/Data/RFCs rfcs.json
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

def main(src_dir, out_path):
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
        wg = pick(meta, FIELD_MAP['wg'])
        if wg and wg.upper() in ('NON WORKING GROUP', 'INDEPENDENT', 'LEGACY', 'IETF - NON WORKING GROUP'):
            wg = None
        out.append({
            'id': f'RFC{int(num.group(1))}',
            'title': pick(meta, FIELD_MAP['title'], ''),
            'abstract': pick(meta, FIELD_MAP['abstract'], '') or '',
            'keywords': kw,
            'wg': wg.lower() if wg else None,
            'status': pick(meta, FIELD_MAP['status']),
            'stream': pick(meta, FIELD_MAP['stream'], ''),
            'year': year, 'month': month, 'day': day,
        })
    json.dump(out, open(out_path, 'w'))
    print(f'wrote {len(out)} records to {out_path}')

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path.home() / 'Data/RFCs')
    dst = sys.argv[2] if len(sys.argv) > 2 else 'rfcs.json'
    main(src, dst)

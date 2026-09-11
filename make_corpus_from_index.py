#!/usr/bin/env python3
"""Build rfcs.json from the RFC Editor's rfc-index.xml.

Usage:  python3 make_corpus_from_index.py [rfc-index.xml] [rfcs.json]
If rfc-index.xml is not present it is downloaded from https://www.rfc-editor.org/rfc-index.xml.

Output: one record per published RFC — id, title, year, month, day, keywords, abstract, draft,
status, stream, area, wg, obsoletes/obsoleted_by/updates/updated_by. `day` is present only when the
index records one, which it does only for the April 1st series; the engine relies on that.
"""
import json, sys, urllib.request, xml.etree.ElementTree as ET

NS = {'r': 'https://www.rfc-editor.org/rfc-index'}

def text(el, tag):
    x = el.find(f'r:{tag}', NS)
    return x.text.strip() if x is not None and x.text else None

def main(src='rfc-index.xml', dst='rfcs.json'):
    try:
        open(src).close()
    except FileNotFoundError:
        print('downloading rfc-index.xml ...')
        urllib.request.urlretrieve('https://www.rfc-editor.org/rfc-index.xml', src)
    root = ET.parse(src).getroot()
    out = []
    for e in root.findall('r:rfc-entry', NS):
        doc_id = text(e, 'doc-id')                       # e.g. RFC9000
        date = e.find('r:date', NS)
        rec = {
            'id': doc_id,
            'title': text(e, 'title'),
            'month': text(date, 'month') if date is not None else None,
            'year': int(text(date, 'year')) if date is not None and text(date, 'year') else None,
            'day': int(text(date, 'day')) if date is not None and text(date, 'day') else None,
            'keywords': [k.text.strip() for k in e.findall('r:keywords/r:kw', NS) if k.text],
            'abstract': ' '.join(p.text.strip() for p in e.findall('r:abstract/r:p', NS) if p.text),
            'draft': text(e, 'draft'),
            'status': text(e, 'current-status'),
            'stream': text(e, 'stream'),
            'area': text(e, 'area'),
            'wg': (text(e, 'wg_acronym') or '').lower() or None,
        }
        for rel in ('obsoletes', 'obsoleted-by', 'updates', 'updated-by'):
            rec[rel.replace('-', '_')] = [d.text for d in e.findall(f'r:{rel}/r:doc-id', NS) if d.text]
        out.append(rec)
    json.dump(out, open(dst, 'w'))
    print(f'wrote {len(out)} records to {dst}')

if __name__ == '__main__':
    main(*sys.argv[1:3])

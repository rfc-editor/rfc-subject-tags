#!/usr/bin/env python3
"""RFC subject tagger: a model reads each RFC with the taxonomy and says which tags it should carry and why.

Usage:  python3 tagger.py                 tag every RFC in rfcs.json that rfc-tags.json has no result for
        python3 tagger.py --retag RFC9000 RFC9001     tag these again
        python3 tagger.py --all           tag the whole corpus again
        python3 tagger.py --no-model      call no model: rebuild rfc-tags.json from what it already holds
        python3 tagger.py --no-model --recheck   also look for every stored quote in the corpus text again

Reads   taxonomy.yaml, assignments.yaml, tagging_instructions.md, rfcs.json, rfc-tags.json (if present)
        and the text of each RFC to be tagged from a local copy of the RFC corpus (--corpus).
Writes  rfc-tags.json: for every RFC its tags, the reasoning for each, the tags considered and
        rejected, subjects the taxonomy lacks, full paths and technology/topic coordinates.

The model is reached through the `claude` command-line program (Claude Code), which each user
installs and signs in to themselves, or runs with ANTHROPIC_API_KEY set. Nothing else is needed.

rfc-tags.json is both the output and the store: a model result is kept there and is not asked for
again unless --retag or --all says so. Everything else in an entry (hand assignments, paths, the
two axes, review reasons) is derived on every run, so --no-model brings the file up to date with
taxonomy.yaml, assignments.yaml and the index without calling the model.
"""
import argparse, collections, concurrent.futures, datetime, hashlib, json, os, pathlib, re, subprocess, sys, threading, time
import engine

MODEL = 'claude-sonnet-5-5'     # the model the instructions were validated with
EFFORT = 'medium'
MAX_CHARS = 300_000             # longer texts are cut here and the entry says so
CACHE = pathlib.Path('.tagger-cache')   # results not yet merged into rfc-tags.json; lets an interrupted run resume
HUMOR = 'humor'                 # R16: a humorous RFC carries this tag and nothing else
MODEL_FIELDS = ('role', 'why', 'quote', 'section')
UNTAGGED = 'not tagged by the model: awaiting a tagger run, or no text in the corpus'

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['summary', 'tags', 'rejected', 'gaps'], 'properties': {
    'summary': {'type': 'string'},
    'tags': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
             'required': ['id', 'role', 'quote', 'section', 'why'],
             'properties': {'id': {'type': 'string'}, 'role': {'type': 'string', 'enum': ['primary', 'secondary']},
                            'quote': {'type': 'string'}, 'section': {'type': 'string'}, 'why': {'type': 'string'}}}},
    'rejected': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['id', 'why'],
                 'properties': {'id': {'type': 'string'}, 'why': {'type': 'string'}}}},
    'gaps': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['name', 'why'],
             'properties': {'name': {'type': 'string'}, 'why': {'type': 'string'}}}}}}

# ---- what the model is given ------------------------------------------------
def system_prompt(tax, instructions='tagging_instructions.md'):
    """The instructions followed by the taxonomy as an indented tree: id, kind and description only.
    Uuids, slugs and statistics are left out."""
    kids = collections.defaultdict(list)
    for t in tax.tags: kids[t.get('parent')].append(t)
    lines = []
    def walk(parent, depth):
        for t in kids[parent]:
            lines.append(f"{'  ' * depth}- {t['id']} [{'topic' if t['kind'] == 'topic' else 'tech'}]: {t.get('desc', '')}")
            walk(t['id'], depth + 1)
    walk(None, 0)
    return open(instructions).read() + '\n\n# Taxonomy\n\n' + '\n'.join(lines) + '\n'

def rfc_text(corpus, rid):
    """The RFC's plain text from the local corpus, lightly cleaned; (None, False) if there is none."""
    p = pathlib.Path(corpus) / f'rfc{rid[3:]}.txt'
    if not p.exists(): return None, False
    txt = re.sub(r'\n{4,}', '\n\n\n', p.read_text(errors='replace').replace('\f', ''))
    if len(txt) > MAX_CHARS: return txt[:MAX_CHARS] + '\n[... text truncated for length ...]', True
    return txt, False

def message(rfc, text):
    return (f"Document: {rfc['id']}\nTitle: {rfc.get('title')}\nPublished: {rfc.get('year')}\nStream: {rfc.get('stream')}\n"
            f"Working group: {rfc.get('wg')}\nStatus: {rfc.get('status')}\n\n===== FULL TEXT =====\n{text}")

# ---- calling the model --------------------------------------------------------
class ModelError(Exception): pass

def ask(prompt_file, msg, model, timeout=900):
    """One RFC in one fresh context. Returns (structured output, model id, cost)."""
    cmd = ['claude', '-p', '--model', model, '--effort', EFFORT, '--tools', '', '--strict-mcp-config',
           '--setting-sources', '', '--no-session-persistence', '--system-prompt-file', str(prompt_file),
           '--output-format', 'json', '--json-schema', json.dumps(SCHEMA)]
    try:
        p = subprocess.run(cmd, input=msg, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise SystemExit('tagger: the `claude` command was not found. Install Claude Code and sign in (see code.md).')
    except subprocess.TimeoutExpired:
        raise ModelError('timed out')
    try: d = json.loads(p.stdout)
    except ValueError: raise ModelError((p.stderr or p.stdout or 'no output').strip()[:300])
    out = d.get('structured_output')
    if d.get('is_error') or not isinstance(out, dict): raise ModelError(str(d.get('result'))[:300])
    return out, next(iter(d.get('modelUsage') or {}), model), d.get('total_cost_usd') or 0

def squash(s):
    """Letters and digits only, lower case: a quote is looked for without regard to line breaks,
    spacing, hyphenation or punctuation, which the model tidies when it copies a passage."""
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def quotable(text):
    """The text as a quote is looked for in it: without the running header and footer of each
    page, which otherwise interrupt any passage that crosses a page break."""
    keep = [l for l in text.split('\n') if not re.search(r'\[Page \d+\]\s*$', l) and not re.match(r'^RFC \d+ .{10,} \w+ \d{4}\s*$', l)]
    return squash('\n'.join(keep))

def quote_found(quote, body):
    parts = [squash(x) for x in re.split(r'\.\.\.|…', quote or '') if squash(x)]   # an elided quote is checked piece by piece
    return bool(parts) and all(x in body for x in parts)

def recheck(store, corpus):
    """Look again for every stored quote in the corpus text, replacing the quote notes. Calls no model."""
    n = 0
    for rid, rec in store.items():
        text, _ = rfc_text(corpus, rid)
        if text is None: continue
        body = quotable(text)
        notes = [x for x in rec['meta']['notes'] if 'quote not found' not in x]
        notes += [f"{t['id']}: quote not found in the text" for t in rec['tags'] if not quote_found(t['quote'], body)]
        n += notes != rec['meta']['notes']; rec['meta']['notes'] = notes
    return n

def tag_one(tax, rfc, corpus, prompt_file, prompt_hash, model, tries=3):
    """Ask the model about one RFC and check what comes back. Returns a store record, or None if the
    corpus has no text for it."""
    text, truncated = rfc_text(corpus, rfc['id'])
    if text is None: return None
    err = None
    for attempt in range(tries):
        try:
            out, used, cost = ask(prompt_file, message(rfc, text), model); break
        except ModelError as e:
            err = e; time.sleep(20 * (attempt + 1))
    else:
        raise err
    notes = ['text truncated at %d characters' % MAX_CHARS] if truncated else []
    body = quotable(text); tags = []
    for t in out['tags']:
        tid = t['id'] if t['id'] in tax.by_id else tax.lookup(t['id'])
        if not tid: notes.append(f"model chose {t['id']!r}, which is not a tag"); continue
        if any(x['id'] == tid for x in tags): continue
        if not quote_found(t.get('quote'), body):
            notes.append(f'{tid}: quote not found in the text')
        tags.append({'id': tid, 'role': t['role'], 'why': t['why'], 'quote': t.get('quote', ''), 'section': t.get('section', '')})
    return {'summary': out['summary'], 'tags': tags, 'rejected': out.get('rejected', []), 'gaps': out.get('gaps', []),
            'meta': {'model': used, 'date': datetime.date.today().isoformat(), 'prompt': prompt_hash, 'notes': notes}, 'cost': cost}

# ---- the store: model results, kept in rfc-tags.json ----------------------------
def from_entry(e):
    """The model's result as recorded in an rfc-tags.json entry, or None if the entry has none."""
    m = e.get('tagged')
    if not m: return None
    why = lambda t: m['removed'][t] if t in m['removed'] else e['reasons'][t]
    return {'summary': e.get('summary', ''), 'rejected': e.get('rejected', []), 'gaps': e.get('gaps', []),
            'tags': [dict(id=t, **{k: why(t)[k] for k in MODEL_FIELDS}) for t in m['tags']],
            'meta': {k: m[k] for k in ('model', 'date', 'prompt', 'notes')}}

def build(tax, rfcs, store):
    """rfc-tags.json from the model results, the hand assignments and the taxonomy. Calls no model."""
    out = {}
    for r in rfcs:
        rid = r['id']; rec = store.get(rid); ov = tax.overrides.get(rid, {})
        tags = []; reasons = {}; review = []; removed = {}   # removed: the model's reasoning for tags the entry does not carry
        if rec:
            review += rec['meta']['notes']
            for t in rec['tags']:
                why = {k: t[k] for k in MODEL_FIELDS}
                if t['id'] not in tax.by_id:
                    review.append(f"{t['id']}: no longer in the taxonomy; tag this RFC again"); removed[t['id']] = why; continue
                tags.append(t['id']); reasons[t['id']] = why
        else:
            review.append(UNTAGGED)
        hand = {'why': ov.get('reason'), 'by': str(ov.get('by', '')), 'date': str(ov.get('date', ''))}
        for t in ov.get('remove', []) or []:
            if t in tags: tags.remove(t); removed[t] = reasons.pop(t)
        for t in ov.get('add', []) or []:
            if t in tags: reasons[t]['hand'] = hand                      # the model chose it too: keep both accounts
            else: tags.append(t); reasons[t] = dict(role='hand', **hand)
        tech, topic = tax.two_axis(tags)
        if HUMOR in tags and len(tags) > 1: review.append(f'{HUMOR} beside other tags (R16)')
        if rec and not tags: review.append('no tags (R7)')
        if tags and not topic: review.append('no topic (R8)')
        e = {'title': r.get('title'), 'year': r.get('year'), 'summary': rec['summary'] if rec else None, 'tags': tags, 'reasons': reasons,
             'rejected': rec['rejected'] if rec else [], 'gaps': rec['gaps'] if rec else [],
             'review': [] if ov else review, 'reviewed': bool(ov),
             'paths': [list(p) for p in sorted({tax.path[t][:i] for t in tags for i in range(1, len(tax.path[t]) + 1)})],
             'technology': tech, 'topic': topic, 'tagged': None}
        if rec:
            e['tagged'] = dict(rec['meta'], tags=[t['id'] for t in rec['tags']], removed=removed)
        out[rid] = e
    # a document and the one that obsoletes it are almost always about the same thing: no tag in
    # common, counting ancestors, means one of the two assignments is probably wrong
    closed = {k: {t for p in v['paths'] for t in p} for k, v in out.items()}
    for r in rfcs:
        for o in r.get('obsoleted_by') or []:
            if o in out and closed[r['id']] and closed[o] and not (closed[r['id']] & closed[o]):
                if not out[r['id']]['reviewed']: out[r['id']]['review'].append(f'no tag in common with {o}, which obsoletes it')
                if not out[o]['reviewed']: out[o]['review'].append(f'no tag in common with {r["id"]}, which it obsoletes')
    return out

def write(out, path='rfc-tags.json'):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False); f.write('\n')
    os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--no-model', action='store_true', help='rebuild rfc-tags.json without calling the model')
    ap.add_argument('--recheck', action='store_true', help='look for every stored quote in the corpus text again (after a change to the check); calls no model')
    ap.add_argument('--retag', nargs='+', metavar='RFCn', default=[], help='tag these RFCs again')
    ap.add_argument('--all', action='store_true', help='tag every RFC again')
    ap.add_argument('--limit', type=int, help='tag at most this many RFCs in this run (lowest numbers first)')
    ap.add_argument('--jobs', type=int, default=6, help='RFCs in flight at once (default 6)')
    ap.add_argument('--model', default=MODEL, help=f'model to ask (default {MODEL})')
    ap.add_argument('--corpus', default=os.environ.get('RFC_CORPUS', os.path.expanduser('~/Data/RFCs')),
                    help='directory holding rfcNNNN.txt (default $RFC_CORPUS or ~/Data/RFCs)')
    a = ap.parse_args()
    tax = engine.Taxonomy('taxonomy.yaml'); tax.load_overrides('assignments.yaml')
    rfcs = engine.load_rfcs('rfcs.json'); known = {r['id'] for r in rfcs}
    try: old = json.load(open('rfc-tags.json'))
    except FileNotFoundError: old = {}
    store = {k: s for k, v in old.items() if (s := from_entry(v))}
    bad = [x for x in a.retag if x not in known]
    if bad: sys.exit(f'tagger: not in rfcs.json: {bad}')

    if not a.no_model:
        prompt = system_prompt(tax); prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        CACHE.mkdir(exist_ok=True); pf = CACHE / f'system-prompt-{prompt_hash}.txt'; pf.write_text(prompt)
        again = known if a.all else set(a.retag)
        todo = sorted((r for r in rfcs if (r['id'] in again if again else r['id'] not in store)), key=lambda r: int(r['id'][3:]))
        for r in list(todo):                                   # results an interrupted run already paid for
            c = CACHE / f"{r['id']}.json"
            if c.exists() and r['id'] not in again:
                rec = json.loads(c.read_text())
                if rec['meta']['prompt'] == prompt_hash: store[r['id']] = rec; todo.remove(r)
        if a.limit: todo = todo[:a.limit]
        print(f'tagger: {len(todo)} RFCs to tag with {a.model}, {a.jobs} at a time; prompt {prompt_hash}', flush=True)
        done = failed = 0; cost = 0.0; notext = []; streak = 0; stop = threading.Event(); lock = threading.Lock()
        def work(r):
            if stop.is_set(): return r, 'skipped'
            try: return r, tag_one(tax, r, a.corpus, pf, prompt_hash, a.model)
            except ModelError as e: return r, e
        with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
            for r, rec in ex.map(work, todo):
                if rec == 'skipped': continue
                if rec is None: notext.append(r['id']); continue
                if isinstance(rec, ModelError):
                    failed += 1; streak += 1; print(f"  {r['id']}: failed: {rec}", flush=True)
                    if streak >= 5 and not stop.is_set():
                        stop.set(); print('tagger: five failures in a row; stopping. Results so far are kept; run again to resume.', flush=True)
                    continue
                streak = 0; done += 1; cost += rec.pop('cost', 0)
                (CACHE / f"{r['id']}.json").write_text(json.dumps(rec)); store[r['id']] = rec
                if done % 100 == 0: print(f'  {done} tagged, {failed} failed, ${cost:.2f} so far', flush=True)
        print(f'tagger: tagged {done}, failed {failed}, reported cost ${cost:.2f}', flush=True)
        if notext: print(f'tagger: no text in {a.corpus} for {len(notext)}: {" ".join(notext)}', flush=True)

    if a.recheck: print(f'tagger: quote notes changed for {recheck(store, a.corpus)} RFCs', flush=True)
    out = build(tax, rfcs, store); write(out)
    carried = collections.Counter(t for v in out.values() for p in v['paths'] for t in p)
    print(f"{len(tax.by_id)} tags; {len(out)} RFCs; not tagged by the model {sum(1 for v in out.values() if not v['tagged'])}; "
          f"untagged {sum(1 for v in out.values() if not v['tags'])}; zero-topic {sum(1 for v in out.values() if v['tags'] and not v['topic'])}; "
          f"unused {len([t for t in tax.by_id if t not in carried])}; needing review {sum(1 for v in out.values() if v['review'])}; "
          f"hand-assigned {sum(1 for v in out.values() if v['reviewed'])}")

if __name__ == '__main__':
    main()

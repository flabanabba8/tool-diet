"""Tool schema weight versus real tool usage. Reads only tool names and counts from the session database, read-only."""
import json
import math
import re
import sqlite3
import time
from pathlib import Path

CHARS_PER_TOKEN = 4.0
NAME = re.compile(r'^[A-Za-z0-9_:.\-]{1,100}$')
PROTECTED = {'terminal', 'file', 'skills', 'memory', 'todo', 'clarify'}


def definition_name(d): return (d.get('function') or d).get('name', '')


def weight(d): return len(json.dumps(d, separators=(',', ':'), ensure_ascii=False))


def est_tokens(chars): return int(math.ceil(chars / CHARS_PER_TOKEN))


def usage(db_path, days):
    """tool name -> calls in the window, and session count. Names and counts only."""
    p = Path(db_path)
    if not p.is_file(): return {}, 0, 'no session database found'
    cutoff = time.time() - days * 86400
    try:
        con = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=5)
        try:
            rows = con.execute('SELECT tool_name, COUNT(*) FROM messages WHERE tool_name IS NOT NULL AND timestamp >= ? GROUP BY tool_name', (cutoff,)).fetchall()
            sessions = con.execute('SELECT COUNT(*) FROM sessions WHERE started_at >= ?', (cutoff,)).fetchone()[0]
        finally: con.close()
    except sqlite3.Error as exc:
        return {}, 0, 'could not read the session database: ' + str(exc)[:100]
    return {n: c for n, c in rows if isinstance(n, str)}, sessions, None


def table(defs, toolset_of):
    sets = {}
    for d in defs:
        n = definition_name(d); ts = toolset_of(n) or 'unknown'; r = sets.setdefault(ts, {'tools': [], 'chars': 0}); r['tools'].append(n); r['chars'] += weight(d)
    return sets


def measure(defs, toolset_of, calls=None):
    sets = table(defs, toolset_of); total = sum(r['chars'] for r in sets.values()) or 1; calls = calls or {}
    rows = [{'toolset': ts, 'tools': len(r['tools']), 'est_tokens': est_tokens(r['chars']), 'share_percent': round(100 * r['chars'] / total, 1), 'calls_in_window': sum(calls.get(t, 0) for t in r['tools'])} for ts, r in sets.items()]
    rows.sort(key=lambda r: -r['est_tokens'])
    return {'tools': len(defs), 'est_tokens_per_request': est_tokens(total), 'toolsets': rows}


def plan(defs, toolset_of, calls, sessions, days, min_calls=1, keep=()):
    m = measure(defs, toolset_of, calls); keep = set(keep) | PROTECTED
    drop = [r for r in m['toolsets'] if r['calls_in_window'] < min_calls and r['toolset'] not in keep and r['toolset'] != 'unknown' and NAME.match(r['toolset'])]
    saved = sum(r['est_tokens'] for r in drop)
    return {'window_days': days, 'sessions_in_window': sessions, 'current_est_tokens_per_request': m['est_tokens_per_request'], 'candidates': drop,
            'est_tokens_saved_per_request': saved, 'percent_of_tool_tokens': round(100 * saved / m['est_tokens_per_request'], 1) if m['est_tokens_per_request'] else 0,
            'commands': [f'hermes tools disable {r["toolset"]}' for r in drop], 'kept_because_used_or_protected': sorted(r['toolset'] for r in m['toolsets'] if r not in drop)[:40],
            'notice': 'Token figures estimate 4 characters per token over the tool schemas and are not billed amounts. A toolset you did not use in this window may still matter next week; nothing was changed. Run the commands yourself if you agree.'}


def whatif(measure_fn, disable):
    before = measure_fn([]); after = measure_fn(list(disable))
    return {'before_est_tokens': before, 'after_est_tokens': after, 'saved_est_tokens': before - after, 'disabled': list(disable)}

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest

root = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('diet_fixture', root / '__init__.py', submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
core = sys.modules['diet_fixture.core']


def fn(name, desc='d' * 100): return {'type': 'function', 'function': {'name': name, 'description': desc, 'parameters': {'type': 'object', 'properties': {}}}}


DEFS = [fn('terminal', 'x' * 200), fn('read_file'), fn('browser_open', 'b' * 900), fn('browser_click', 'b' * 900), fn('image_generate', 'i' * 600), fn('web_search', 'w' * 300)]
OWNER = {'terminal': 'terminal', 'read_file': 'file', 'browser_open': 'browser', 'browser_click': 'browser', 'image_generate': 'image_gen', 'web_search': 'web'}.get


class DietTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = str(Path(self.tmp.name) / 'state.db'); con = sqlite3.connect(self.db)
        con.execute('CREATE TABLE sessions (id TEXT, started_at REAL)'); con.execute('CREATE TABLE messages (tool_name TEXT, timestamp REAL, content TEXT)')
        now = time.time(); con.execute('INSERT INTO sessions VALUES ("a", ?), ("old", ?)', (now - 3600, now - 90 * 86400))
        for name, n, age in (('terminal', 30, 3600), ('read_file', 10, 3600), ('web_search', 2, 3600), ('image_generate', 5, 90 * 86400)): con.executemany('INSERT INTO messages VALUES (?, ?, ?)', [(name, now - age, 'secret content that must never be read')] * n)
        con.commit(); con.close()

    def tearDown(self): self.tmp.cleanup()

    def test_usage_counts_names_only_inside_the_window(self):
        calls, sessions, note = core.usage(self.db, 30); self.assertEqual((calls, sessions, note), ({'terminal': 30, 'read_file': 10, 'web_search': 2}, 1, None))

    def test_measure_ranks_toolsets_by_weight_and_shows_calls(self):
        m = core.measure(DEFS, OWNER, core.usage(self.db, 30)[0]); top = m['toolsets'][0]
        self.assertEqual((top['toolset'], top['tools'], top['calls_in_window']), ('browser', 2, 0)); self.assertAlmostEqual(sum(r['share_percent'] for r in m['toolsets']), 100, delta=0.5)

    def test_plan_drops_only_unused_unprotected_toolsets_with_exact_commands(self):
        calls, sessions, _ = core.usage(self.db, 30); p = core.plan(DEFS, OWNER, calls, sessions, 30)
        self.assertEqual(sorted(r['toolset'] for r in p['candidates']), ['browser', 'image_gen']); self.assertEqual(sorted(p['commands']), ['hermes tools disable browser', 'hermes tools disable image_gen'])
        self.assertGreater(p['percent_of_tool_tokens'], 40); self.assertIn('nothing was changed', p['notice'])

    def test_keep_min_calls_and_protected_sets_are_respected(self):
        calls, sessions, _ = core.usage(self.db, 30)
        self.assertEqual([r['toolset'] for r in core.plan(DEFS, OWNER, calls, sessions, 30, keep=['browser'])['candidates']], ['image_gen'])
        self.assertIn('web', [r['toolset'] for r in core.plan(DEFS, OWNER, calls, sessions, 30, min_calls=3)['candidates']])
        self.assertNotIn('terminal', [r['toolset'] for r in core.plan(DEFS, OWNER, {}, 0, 30)['candidates']])

    def test_missing_or_broken_database_is_reported_not_raised(self):
        self.assertEqual(core.usage('/nonexistent/state.db', 30)[2], 'no session database found')
        bad = Path(self.tmp.name) / 'bad.db'; bad.write_text('not a database'); self.assertIn('could not read', core.usage(str(bad), 30)[2])

    def test_whatif_uses_the_assembler_callback(self):
        out = core.whatif(lambda d: 1000 - 100 * len(d), ['browser', 'web']); self.assertEqual((out['before_est_tokens'], out['after_est_tokens'], out['saved_est_tokens']), (1000, 800, 200))

    def test_database_is_opened_read_only(self):
        before = Path(self.db).read_bytes(); core.usage(self.db, 30); self.assertEqual(Path(self.db).read_bytes(), before)

    def test_tool_layer_rejects_bad_names(self):
        module._env = lambda: (lambda d=(): DEFS, OWNER, self.db)
        self.assertIn('error', json.loads(module.invoke('diet_whatif', {'toolsets': ['x; rm -rf /']})))
        self.assertIn('candidates', json.loads(module.invoke('diet_plan', {'days': 30})))


if __name__ == '__main__': unittest.main()

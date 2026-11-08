import json
from . import core


def _env():
    import model_tools
    from hermes_constants import get_hermes_home
    from tools.registry import registry

    def defs(disabled=()): return model_tools.get_tool_definitions(disabled_toolsets=list(disabled) or None, quiet_mode=True)
    def toolset_of(name):
        e = registry.get_entry(name, scope=registry.current_scope_key())
        return getattr(e, 'toolset', None) if e else None
    return defs, toolset_of, str(get_hermes_home() / 'state.db')


def invoke(name, args):
    try:
        defs, toolset_of, db = _env()
        if name == 'diet_measure':
            calls, sessions, note = core.usage(db, args.get('days', 30)); out = core.measure(defs(), toolset_of, calls)
            return json.dumps({**out, 'window_days': args.get('days', 30), 'sessions_in_window': sessions, **({'warning': note} if note else {})})
        if name == 'diet_plan':
            days = args.get('days', 30); calls, sessions, note = core.usage(db, days)
            if note: return json.dumps({'error': note})
            return json.dumps(core.plan(defs(), toolset_of, calls, sessions, days, args.get('min_calls', 1), args.get('keep', [])))
        disable = args['toolsets']
        if not isinstance(disable, list) or not all(isinstance(x, str) and core.NAME.match(x) for x in disable): raise ValueError('toolsets must be a list of toolset names')
        return json.dumps(core.whatif(lambda d: core.est_tokens(sum(core.weight(x) for x in defs(d))), disable))
    except (ValueError, TypeError, OSError, KeyError, ImportError) as exc:
        return json.dumps({'error': str(exc)})


S = {'type': 'string'}
TOOLS = {
    'diet_measure': ('Estimate the tokens the currently enabled tool definitions cost on every request, per toolset, next to how many times each toolset was actually called in your recent sessions (tool names and counts only).', {'days': {'type': 'integer', 'minimum': 1, 'maximum': 365}}, []),
    'diet_plan': ('Propose which toolsets to disable because they were not called in the window, with estimated tokens saved per request and the exact `hermes tools disable` commands. Changes nothing.', {'days': {'type': 'integer', 'minimum': 1, 'maximum': 365}, 'min_calls': {'type': 'integer', 'minimum': 1}, 'keep': {'type': 'array', 'items': S}}, []),
    'diet_whatif': ('Re-assemble the real tool definitions with the named toolsets disabled and report the estimated token change.', {'toolsets': {'type': 'array', 'items': S}}, ['toolsets']),
}


def register(ctx):
    for name, (description, properties, required) in TOOLS.items():
        ctx.register_tool(name=name, toolset='tool_diet', schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}},
            handler=lambda args, _name=name, **kwargs: invoke(_name, args))

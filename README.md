# Tool Diet

Every request carries the definitions of every enabled tool, whether or not the agent will use them. Tool Diet puts a number on that and compares it with what you actually call.

- `diet_measure` assembles the tool definitions Hermes currently sends (through Hermes's own `get_tool_definitions`), estimates tokens per toolset (4 characters per token over the JSON schemas, an estimate and not a billed amount), and shows each toolset's share next to the number of times its tools were called in your last N sessions.
- `diet_plan` proposes toolsets to turn off because they were not called in the window (default 30 days, adjustable with `min_calls` and a `keep` list; terminal, file, skills, memory, todo and clarify are always kept), with estimated tokens saved per request and the exact `hermes tools disable <toolset>` commands. **It changes nothing**; you run the commands if you agree.
- `diet_whatif` re-assembles the real definitions with named toolsets disabled and reports the estimated change, so the figure reflects how Hermes actually builds the list (it can differ from the plan's per-toolset sum).

Usage comes from Hermes's own session database, opened read-only: only tool names and counts are read, never message content.

Limits: the token numbers are estimates and prompt caching changes what a saved token costs; a toolset unused this month may matter next month; the plan sees only this profile's history; MCP tools and tools Hermes loads on demand may be grouped differently from how you think of them; Hermes also has its own tool-search assembly, which this complements rather than replaces. Disabling a tool removes a capability, so read the list before you run anything.

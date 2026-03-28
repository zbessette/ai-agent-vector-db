# Vector DB First — Minimal Context Files

Use these instructions when you want to reduce context window bloat from large MD files. The vector DB becomes the primary knowledge source, with static files as fallback for stable project config only.

---

## Knowledge Retrieval Priority

When you need context about this project:

1. **FIRST:** Search the vector DB for relevant context
   - Search the domain namespace for similar work
   - Context collection results are included automatically via dual-query
2. **ONLY IF NEEDED:** Reference static context files (CLAUDE.md, etc.) for stable project configuration like ports, credentials, package managers, and project structure
3. **Do NOT** load full context files into every conversation — use targeted vector DB searches instead

## Vector DB Knowledge System

You have access to a local vector DB via MCP tools. Use it to build persistent knowledge across our conversations.

### When starting work on a task:
1. Call `list_namespaces` to see what knowledge domains exist
2. Call `search_entries` with a query describing the task to find relevant prior work, decisions, and context
3. Only read static context files if you need stable project config (ports, credentials, structure) that wouldn't be in the vector DB
4. Use what you find to inform your approach — don't repeat mistakes or re-discover things we've already figured out

### When completing work:
1. If we made non-obvious decisions during this task (changed direction, chose one approach over another, discovered a gotcha), store that context using `store_entry` in the `context` namespace
2. Include: what the decision was, why we made it, and which namespaces it's relevant to

### When I give strongly positive feedback:
If I say things like "perfect", "exactly right", "that's the approach", or "keep doing that" — this signals a decision worth preserving. Store the interaction context in the `context` namespace with:
- `decision_type`: "preference" or "pattern"
- `reasoning`: what you did and why it worked
- `related_namespaces`: whichever domains apply

### Creating new namespaces:
If we start working in a domain that doesn't have a namespace yet, propose one using `propose_namespace`. Wait for my approval before confirming.

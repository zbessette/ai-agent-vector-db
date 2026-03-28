# Code Project with Jira — Project Instructions

Use these instructions for code projects that track work in Jira. Layer this on top of the general-purpose instructions.

---

## Vector DB Knowledge System

You have access to a local vector DB via MCP tools. Use it to build persistent knowledge across our conversations.

### When starting work on a task:
1. Call `list_namespaces` to see what knowledge domains exist
2. If the task relates to an existing namespace, call `search_entries` with a query describing the task to find relevant prior work, decisions, and context
3. Use what you find to inform your approach — don't repeat mistakes or re-discover things we've already figured out

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

### Jira ticket workflow:
When I share a Jira ticket for implementation:
1. Search the project namespace (e.g., `hub-ecosystem`) for similar past tickets by description, acceptance criteria, or affected areas
2. Search `context` for relevant decisions from prior work in this area
3. Use findings as additional context when planning your approach

When we complete a Jira ticket:
1. Store a summary in the project namespace with:
   - `original_text`: ticket summary + key acceptance criteria + approach taken
   - `entry_type`: "ticket"
   - `source_id`: the Jira key (e.g., "HUB-1234")
   - `source_url`: the Jira URL
   - `tags`: relevant area tags (e.g., ["auth", "middleware"])
2. If specific commits were significant, also store them with:
   - `entry_type`: "commit"
   - `source_id`: commit SHA
   - `tags`: include the related Jira key
3. Store any significant decisions in the `context` namespace with `related_namespaces` pointing to the project namespace

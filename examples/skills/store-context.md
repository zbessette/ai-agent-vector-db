# store-context

Capture decision context from the current conversation into the vector DB. Use when completing a task, after positive feedback, or when a significant decision was made.

## Usage

- `/store-context` — Interactive mode, asks what to store
- `/store-context decision` — Store a decision in the context namespace
- `/store-context ticket PROJ-123` — Store ticket completion context in a project namespace

## Interactive mode

When called without arguments:

1. Summarize the key decisions or outcomes from the current conversation
2. Ask the user which items are worth storing
3. For each confirmed item, determine:
   - Is this a cross-cutting decision? -> `context` namespace
   - Is this project-specific knowledge? -> the relevant project namespace
4. Format and store using `store_entry`
5. Confirm what was stored

## Decision mode (`/store-context decision`)

Store a decision in the `context` namespace:

1. Summarize the decision from the current conversation context
2. Present to the user for confirmation
3. Call `store_entry` with:
   - `namespace`: "context"
   - `original_text`: description of the decision and its context
   - `entry_type`: "decision"
   - `payload`:
     - `related_namespaces`: infer from conversation, or ask
     - `decision_type`: one of "direction_change", "preference", "pattern", "constraint"
     - `reasoning`: why this decision was made

## Ticket mode (`/store-context ticket PROJ-123`)

Store ticket completion context in a project namespace:

1. Ask which namespace this ticket belongs to (or infer from context)
2. Gather: ticket summary, acceptance criteria, approach taken, key commits
3. Call `store_entry` with:
   - `namespace`: the project namespace
   - `original_text`: combined ticket context + approach summary
   - `entry_type`: "ticket"
   - `payload`:
     - `source_id`: the Jira key
     - `source_url`: Jira URL if available
     - `tags`: relevant area tags
4. If significant decisions were made during the ticket, also store those in `context`

## Example interactions

**After completing a refactor:**
```
User: /store-context decision
Claude: During this conversation, we decided to use the repository pattern
        instead of direct DB queries in the auth module because it makes
        testing easier and isolates the migration path. Store this?
User: Yes
Claude: Stored in context namespace:
        - decision_type: "pattern"
        - related_namespaces: ["hub-ecosystem"]
        - reasoning: "Repository pattern chosen for auth module to simplify
          testing and isolate future migration path"
```

**After closing a Jira ticket:**
```
User: /store-context ticket HUB-456
Claude: I'll store the completion context for HUB-456 in hub-ecosystem:
        - Summary: Added rate limiting to the GraphQL API
        - Approach: Used express-rate-limit with Redis backing store
        - Key commits: abc123f, def456a
        - Tags: ["api", "rate-limiting", "redis"]
        Store this?
User: Yes
Claude: Stored in hub-ecosystem. Also storing the Redis decision in context
        since it affects infrastructure choices across projects.
```

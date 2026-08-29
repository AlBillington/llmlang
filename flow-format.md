# llmlang Flow — Generated View (draft)

Status: `.llmflow` is a generated, non-canonical companion artifact to a `.llm` file. There is nothing to author here directly — every `→ call` / `← return` line lives in an entry's own llmlang bullets (see [llmlang-format.md](llmlang-format.md) §4e/§4f for that syntax), and a flow file is composed from them. It exists purely to give a human a flattened, order-following trace of one entry point's execution, instead of following the call graph by hand across the `.llm` tree's folder/file/class structure.

For the concrete syntax that produces this file (`@entry-point`, `→ call`, `← return`), see [llmlang-format.md](llmlang-format.md) §4e and §4f.

## 1. What generates a flow file

`llmlang build` and `llmlang finalize` regenerate `<stem>.llmflow` from `<stem>.llm` every time they run, unconditionally overwriting whatever was checked in — the same treatment `<stem>.llmlock` already gets. If a `.llm` file has no `@entry-point` entries at all, no `.llmflow` file is written (and any stale one from a removed `@entry-point` is deleted).

The algorithm, per `@entry-point` entry found:

1. Start a new section headed by the entry's label — its own text after `@entry-point(...)`, or `<canonical name> (<summary>):` when the bare form was used.
2. Render the entry's own bullets in order, at one level of indentation. `~ ` test bullets are never rendered - a flow view is about execution, not test coverage, and they're excluded regardless of whether the covered entry has any. A plain `- returns ...` bullet (the accepts/returns bookend, [llmlang-format.md](llmlang-format.md) §4b) renders with `← ` instead of `- `, the same as an explicit `← return ...` line - no need to author the arrow form just for this common case.
3. For every `→ call CanonicalName` bullet encountered, resolve the target to exactly one llmlang entry (by exact canonical name or unique suffix match) and, the *first* time that entry is reached anywhere in this section's trace, inline its own bullets recursively, one level deeper. A repeat reference to an already-expanded entry — including a direct or indirect cycle — renders as a bare `→ call` line with nothing nested under it.
4. A `→ call ... via ExternalService` bullet is left as-is; there's no local entry to resolve or expand.

Every `@entry-point` entry across the whole `.llm` file becomes its own section in the one `.llmflow` file, in tree order — the same one-`.llmflow`-per-`.llm` convention as before, just generated instead of hand-assembled.

## 2. What `check` verifies

Two independent things, both surfaced as ordinary findings alongside everything else `check` reports for the file:

- **`FLOW_ERROR`** — some `→ call` target reachable from an `@entry-point` entry doesn't resolve to exactly one known entry (missing, or ambiguous). Named by the entry whose own bullets contain the bad line, since that's where the fix belongs. This is the only way flow generation can fail; a single bad line doesn't take down the rest of the file's report.
- **`FLOW_FILE_STALE`** — regenerating from the current `.llm` and code produces text that doesn't match what's checked in. This covers both an entry's bullets or code moving on without a rebuild (already independently caught as that entry's own `SPEC_DIVERGED`/`CODE_DIVERGED`) and the case those can't catch: someone hand-editing the generated `.llmflow` file directly, against convention.

Neither finding requires a disposition of its own in `<stem>.llmchanges.json`. A `→ call` line is just part of its owning entry's text, so editing one already flags that entry's ordinary `SPEC_DIVERGED` and goes through the same disposition gate every other bullet edit does — there's nothing flow-specific left to separately account for. `FLOW_FILE_STALE` is resolved by rebuilding, not by a human judgment call.

## 3. Worked example

Given, in the `.llm` file:

```
@entry-point(GET /users/{id}: returns one user)
find_user (looks up a user by id):
	→ call UserRepository.load
	- returns the user, or nothing if no user has that id

UserRepository.py:
	load (reads a user record by id):
		→ call read a row via UserRepository table with user_id
		- returns the row mapped to a user, or nothing
```

The generated `.llmflow`:

```
GET /users/{id}: returns one user
	→ call UserRepository.load
		→ call read a row via UserRepository table with user_id
		← returns the row mapped to a user, or nothing
	← returns the user, or nothing if no user has that id
```

`find_user` itself is the `@entry-point`, so its own bullets render directly under the header — there's no `→ call find_user` wrapper, since the header line already means "execution starts here."

Note there is nothing here that isn't also true reading the `.llm` file directly — the flow file adds no information, only a different, execution-ordered arrangement of the same facts.

# llmlang — Format & Grammar Spec (v0.2)

Status: the concrete syntax and writing conventions for llmlang source files (`.llm`): what to type and how to structure it. For what llmlang is for, the compilation/review model, the lockfile mechanism, and known limitations, see the [concept doc](readme.md).

## 1. Terms

- **Folder** — a header with no file extension (`Backend:`). Contains more folders or files. Purely organizational.
- **File** — a header with a file extension (`UrlShortener.py:`). The physical location a Component's code lives in, resolved directly from the folder chain above it plus its own name — no separate discovery step or manifest, ever.
- **Class** — a header, inside a file, whose own children are further headers (not bullets). A grouping, needed only when one file holds more than one such grouping (multiple classes sharing a file, or a flat module that happens to need one).
- **Named entry** — a header, inside a file or class, whose own children are `- ` behavior bullets or `~ ` test bullets. The thing that gets a comment handle and maps to exactly one method or property. A named entry header is written `identifier (one-line summary):`; the identifier supplies the final segment of the entry's canonical name, and the summary is the exact source comment text before the canonical-name `[llm:...]` handle, subject only to language comment syntax. *Shape-inferred*, not keyword-driven: whichever kind of children a header has decides what it is.
- **Data entry** — a source-handled entry, inside a file or class, written `identifier data (one-line summary):`. It maps to a concrete named data shape or state field in source with the same `[llm:<canonical-name>]` handle rule as a named entry. Its bullets describe the contained data shape, not behavior; see §4d.
- **Behavior bullet** — one plain-English sentence, `- ` prefixed. Any number of behavior bullets under one named entry all describe that entry together — no one-bullet-per-entry limit. A bare behavior bullet sitting directly on a file or class (not under any entry) is a class/file-level bullet. A behavior bullet may have nested `- ` bullets under it when the nested lines are part of that same behavior statement, most often for decisions and repeats (§4c); nested bullets are not separate entries.
- **Test bullet** — one plain-English sentence, `~ ` prefixed, nested under a named entry, file, or class. The text is the exact source test comment text before `[llm-test:<canonical-node>]`; see §4.
- **Reference** — a plain-English mention of another entry or Component's exact name inside a bullet (`uses CredentialHasher for password verification`). Not special syntax. When a behavior depends on another local entry being called, the bullet must name that entry instead of only describing the effect (`generates the report using buildReportRows`, not `generates the report`).
- **Hint** — optional freetext after a folder/file/class header's name, before its colon (`Printer.js class:`). A header's real name is always its first word; a hint is everything after it. Not enforced, not tracked, not hashed, not a fixed vocabulary — the parser discards it the moment the name's extracted. It exists purely for whoever's reading the raw file, human or compiler, as a clarifying note — a hint states something explicitly that was already true, it never changes what a header is. Named entries and data entries use the required parenthesized summary form instead of hints.

  Shape-inference (§1's Class/Named entry split) already resolves *tree* shape correctly on its own, but it can't distinguish one case that comes up constantly: a File whose direct entries are one implicit class's methods (the common single-class-per-file case, no separate Class node needed) produces the exact same tree shape as a File whose direct entries are a flat module of unrelated standalone functions. The hint convention exists specifically to close that one gap:
  - A **File** header gets a `class` hint when its direct entries are one implicit class's methods/fields with no separate Class node — e.g. `Printer.js class:`, `CodeGenerator.py class:`. It gets no hint when its direct entries are a flat module of standalone functions with no implied class.
  - A genuine nested **Class** node (used only when a file holds more than one class) also gets a `class` hint, for the same at-a-glance legibility, even though shape-inference already resolves it correctly on its own — e.g. `NotesStore class:` inside a `notes.py:` that also holds `NotesValidator class:`.
  - A **named entry** gets a parenthesized one-line summary instead of a hint — e.g. `parse (parses a tab-indented llmlang file into a tree):`, `formatCurrency (formats cents as a currency string):`.
  - A **data entry** gets the `data` marker plus a parenthesized one-line summary — e.g. `gameState data (stores current game state):`, `_code_to_url data (stores a mapping of short code to original URL):`.

  Applied consistently once a file's own shape (implicit class, flat functions, or a mix) is judged — not added ad hoc where clarity seemed to matter.

### 1a. Scope: no entry for pure constant data

A file or entry with no behavior at all — a static lookup table, a seed/config array, literal values nothing computes from — is not described in llmlang, not even minimally. Prose is a poor format for literal data, and nothing about reconstruction needs it: another bullet that depends on the constant can just name it (`uses colorCodes to look up the display color`, per the Reference convention in §1) without the constant needing its own entry to reference. The line: **state shape** (what fields a piece of mutable state tracks and what they mean, e.g. `gameState`) is architecturally meaningful and stays in llmlang like any other data entry; **literal seed/constant values** (the specific hex codes, the specific rows of a static table) are not, and don't.

## 2. Formatting rules

- Indentation is exactly one tab per nesting level. No spaces.
- Every line is a header (ends in `:`), a behavior bullet (`- ` prefixed), a test bullet (`~ ` prefixed), or `@policy:`.
- `@policy:` is the *only* reserved word, valid at root, folder, file, or class scope. Everything else is shape-inferred (§1).
- A header with a `.` in its name is a file (extension = everything after the last `.`); folders may contain folders or files, nothing else.
- Class vs. named entry is decided by what shows up first among a header's *header* children, not its first child overall — a class may legitimately open with a class-level bullet before its first named entry.
- A header's name is its first word. A parenthesized suffix on a named entry or data entry is the required summary; other freetext after a folder/file/class name is an optional Hint (§1), discarded once the name's extracted.
- A data entry uses `data` immediately after its identifier and before its parenthesized summary. It is valid only inside a file or class.
- A regular `- ` bullet may be nested under another regular `- ` bullet. The nested bullet belongs to the same nearest entry, file/class bullet group, or policy item as its parent.
- A `~ ` test bullet may not be nested under another bullet.
- Keep `~ ` test bullets directly attached to the bullets they cover: do not put a blank line between an entry's behavior bullets and its test bullets.
- When an entry ends with `~ ` test bullets, put one blank line before the next header so the next entry is visually separated from the test block.

## 3. Structure grammar (informal)

```
llmlang  := (Policy | Folder | File)*
Folder   := Name Hint? ":" NEWLINE (Policy | Folder | File)*
File     := Name "." Ext Hint? ":" NEWLINE (Policy | Bullet | Class | Entry | DataEntry)*
Class    := Name Hint? ":" NEWLINE (Policy | Bullet | Entry | DataEntry)*
Entry    := Name " (" Summary ")" ":" NEWLINE (Bullet | Test)+
DataEntry := Name " data (" Summary ")" ":" NEWLINE Bullet+
Policy   := "@policy:" NEWLINE Bullet+
Bullet   := "- " Sentence NEWLINE Bullet*
Test     := "~ " Sentence NEWLINE
```

## 4. Test Bullets

A `~ ` bullet records behavior that is covered by an existing test. Put it under the nearest llmlang node whose behavior the test asserts: an entry for one entry's behavior, or a file/class node for cross-entry behavior. By convention, test text is phrased as `should ...`, but this is not a parser rule and not a test identity key. The `~` text is not a generated test name and does not create a separate canonical test identity; it is the human-readable test comment text.

Each `~` bullet must have a matching source/test comment somewhere under the `.llm` file's root:

```python
# should return nothing for an unknown short code [llm-test:Backend.UrlShortener.get_url]
def test_get_url_unknown():
    ...
```

The comment text before `[llm-test:...]` must exactly match the `~` bullet text, and the handle must be the canonical name of the tested entry, file, or class node. A test that covers multiple entries should usually link to the nearest owning file/class node, not duplicate the same test comment under every participating entry.

The lockfile records each linked test trace by explanation text, relative source path, and backing code hash. It deliberately does not store source excerpts; test-code drift is hash-based. The builder refuses both directions of broken linkage: a `~` bullet with no matching test comment, and a stale `llm-test` comment with no matching `~` bullet. The checker reports missing links, stale links, moved/new traces, and backing test code changes without relying on line numbers.

## 4a. "?" bullets — flagging suspected bugs, without deciding to fix them

A bullet prefixed `- ? ` states something the code genuinely does that looks unintentional — a real behavior, described faithfully ([the concept doc](readme.md) §4's "describe, don't decide" applies here too), just flagged for a human to look at rather than silently corrected or silently left unremarkable.

Non-functional/performance claims follow a hard rule regardless of where they live: only valid if quantified enough to become an actual assertion ("responds within 200ms for lists under 10k"). "Should feel fast" is not valid llmlang.

## 4b. Inputs/outputs — bookend bullets, by convention

Where there's something to say, two separate single-purpose bullets frame the entry: an "accepts X" bullet as the *first* bullet, and a "returns Y" bullet as the *last* — the behavioral bullets sit between them. Either half is omitted when there's nothing to say — a function with no parameters gets no accepts bullet, a function with no return value gets no returns bullet, and a void no-arg function gets neither. Constructors are a special case: what they're constructed *from* matters and gets an accepts bullet ("accepts a name, size, width, and value"), but what they return is definitionally the new instance, which carries no information worth stating — a constructor never gets a returns bullet.

Never state the return value twice. If a regular behavioral bullet already says what's returned — most often because it already starts with "returns" itself ("returns whether the roll's original size is zero or less") — that bullet already *is* the closing returns bullet; it does not get a second, more generic "returns Y" bullet stacked next to it restating the same fact in vaguer words. Only add a standalone returns bullet when no existing bullet already states the return value explicitly. This makes the returns half of the convention closer to "make sure the return value is stated exactly once, and that whichever bullet does it sits last" than "always append a bullet."

## 4c. Decisions and repeats

When a behavior needs visible branching, make the parent bullet only the thing being checked or chosen; put outcomes on nested bullets. For a yes/no branch, use `checks whether ...` and nest `if yes` / `if no` outcomes:

```
- checks whether the ticket has a stored original assignee
	- if yes, uses that original assignee
	- if no, keeps the current eligible assignee
```

For a multi-way choice, use `chooses ... by ...` and put each outcome underneath. Keep result detail out of the parent so the branch axis remains obvious.

For loops, prefer `repeats`. The parent bullet states what is repeated and the boundary (`for each ...`, `until ...`, or `at most ...`); nested bullets state the repeated body:

```
- repeats assignment selection for each ticket in due-time order
	- filters agents to the ticket's eligible segment
	- chooses the eligible agent with the lowest total load
```

## 4d. Data entries

A data entry is written `Name data (one-line summary):` and requires a matching source handle immediately before the concrete data definition, field, type, or schema it describes:

```python
# stores a mapping of short code to original URL [llm:Backend.UrlShortener._code_to_url]
self._code_to_url = {}
```

Data bullets describe contained data shape. `stores` is implied by the data-entry kind, so the bullets should be concise type-first descriptions rather than behavior sentences. Every leaf field bullet takes the fixed form `type (example): description` — a type keyword, a concrete example value in parens, then the description. This form is always the same regardless of how simple or complex the shape is; there is no lighter-weight alternative for a single field and no judgment call about when to use it. The type is one of `text`, `number`, `boolean`, `date`, `timestamp`, `[type]` for a one-line-simple list, or the exact named domain/data type when one exists. The example is what actually pins down precision an abstract type name alone can't — whether `number` means an integer or allows fractional values, whether a string field is genuinely a `timestamp` type in the target language or just text that looks like a date. A grouping header (an anonymous nested object, or `mapping:` for an arbitrary-key lookup) carries no type or example itself, since it isn't a scalar value — only its own nested leaf fields do.

```
CustomerProfile data (stores customer profile data):
	- text ("Jane Doe"): customer display name
	- number (3): billing tier rank
	- boolean (true): whether the customer can submit premium tickets
	- timestamp ("2026-01-15T10:30:00Z"): when the customer was created
	- [text] (["jane@work.com", "jane@personal.com"]): alternate email addresses
	- Plan ("Pro"): active billing plan
	- notification preferences:
		- boolean (true): whether email updates are enabled
		- [text] (["promotions", "digests"]): muted topic names
	- mapping:
		- text ("support-team-a"): lookup key is the support team slug
		- number (5): value is the open ticket count for that team
```

## 4e. Cross-entry calls and orchestration entries

When an entry coordinates other entries, describe the observable orchestration by naming the concrete entries it uses. A bullet should not hide a call behind only its downstream effect. This is especially important for `main`, cron handlers, controllers, batch processors, and other top-level flow entries where the main behavior is delegation.

Good:

```
main (processes data subject deletion requests):
	- creates a production Automator using create_production
	- fetches tickets using fetch_tickets_to_process
	- gathers ticket data using get_data_for_tickets
	- writes reports and deletion state using process_and_write_results
```

Too vague:

```
main (processes data subject deletion requests):
	- creates an automator
	- fetches tickets
	- gathers data
	- writes reports and deletion state
```

This is still not a request for procedural pseudocode. Do not list private implementation steps merely because they are adjacent in source. Name another entry when that entry is part of the architecture-level contract: the current entry delegates meaningful behavior to it, a reader would need the dependency to reconstruct or review the flow, or omitting the name would make the call graph invisible.

## 5. Single-sourcing discipline

A behavior is described in exactly one named entry. A second entry that needs it does not restate it — it References the owning entry by name. Not automated: near-duplicate bullets with no Reference between them is a defect caught in **human/AI review**, catchable specifically because llmlang stays terse enough that duplication is visible at a glance — the same duplication invisible across thousands of lines of real code becomes obvious as two similar bullets sitting near each other.

## 6. Completeness — enough detail to reconstruct, not a summary

Bullets must fully specify the *behavior* they describe — exact thresholds, formulas, timing values, and edge-case outcomes — not a high-level gist a reader would need to check the code to fill in. The target is **behavioral** reconstruction: regenerating code from llmlang alone should produce something that behaves identically when tested, even though the exact code (naming, style, structure) is still expected to vary between compiles — [the concept doc](readme.md) §2.1's non-determinism is fully still in play, this is about the spec being complete, not the output being deterministic.

This does not reopen the "no control flow, no algorithms" boundary from [the concept doc](readme.md) §1. The distinction is **declarative vs. procedural**, not **detailed vs. vague**: describe *what must be true* — a rule, a constraint, an outcome — never *the steps to compute it*. "Never adds more mass in one tick than the printer's speed, the filament remaining, or the part's remaining unprinted mass" is a complete, precise rule a compiler can satisfy however it wants (a `min()` call, three sequential clamps, whatever) — it is not pseudocode, and it is not vague either. A bullet that only gestures at the gist ("adds mass at the printer's speed") isn't detailed vs. undetailed so much as *incomplete* — it's silently missing a real constraint.

Completeness and test bullets are related but not the same move. When a human and the compiler are actively deciding what's worth guaranteeing — greenfield authoring, or reviewing a proposed addition ([the concept doc](readme.md) §2.2) — pairing a precise rule with a `~` bullet and matching test comment is the right instinct, since someone is there to approve that it's actually worth asserting as a permanent guarantee. During extraction specifically ([the concept doc](readme.md) §4, and the onboarding methodology it points to), that approval hasn't happened yet: a rule gets written completely as a regular bullet and verified true against the real code, but does not become a `~` bullet unless a test for it already existed in the source. Asserting a new guarantee is a decision, not a description, and extraction only describes.

## 7. Worked example

```
Backend:
	@policy:
		- failures are handled gracefully and never crash the app

	UrlShortener.py class:
		~ should return the original URL for a code that was previously created

		create_short_code (creates a unique short code for a given long URL):
			- accepts a long URL
			- creates a unique short code for a given long URL
			- uses CodeGenerator to generate the code
			- generated codes must be unique per URL
			~ should return the same code when called twice with the same URL
			- returns the short code

		get_url (looks up the original URL for a given short code):
			- accepts a short code
			- looks up the original URL for a given short code
			~ should return not found for an unknown short code
			- returns the original URL

		_code_to_url data (stores a mapping of short code to original URL):
			- mapping:
				- text ("aB3xY9"): lookup key is the short code
				- text ("https://example.com/page"): value is the original URL

	CodeGenerator.py class:
		generate (generates a random 6-character alphanumeric code):
			- generates a random 6-character alphanumeric code
			- returns the generated code

Frontend:
	ShortenerUI.html:
		form (shows a text input for a long URL and a submit button):
			- shows a text input for a long URL and a submit button

		shortenUrl (uses UrlShortener to create a short code when submitted):
			- accepts the long URL
			- uses UrlShortener to create a short code when submitted
			- returns the short code

		renderShortUrl (displays the resulting short URL as a clickable link):
			- accepts the short code
			- displays the resulting short URL as a clickable link to the original URL
```

## 8. Layout convention

Folder-per-Domain, file-per-Component is inherited directly from the llmlang tree — a file's own header carries its extension, and the folder chain above it carries its path, so `Backend/UrlShortener.py:` resolves to exactly that path with zero manifest and zero discovery step. A llmlang tree is a direct map to implementation layout: folder headers map to directories, file headers map to files, and grouping headers inside a file map to real class-like groupings or flat module structure in the code. Any grouping introduced in llmlang must be reflected in the source organization it names. This is a hard requirement for native (non-onboarded) code — see [the concept doc](readme.md) §4 for what happens when it doesn't hold.

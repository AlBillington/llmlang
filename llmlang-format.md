# llmlang — Format & Grammar Spec (v0.2)

Status: the concrete syntax and writing conventions for llmlang source files (`.llm`) — what to type and how to structure it. For what llmlang is for, the compilation/review model, the lockfile mechanism, and open questions, see the concept doc (`llmlang-concept.md`).

## 1. Terms

- **Folder** — a header with no file extension (`Backend:`). Contains more folders or files. Purely organizational.
- **File** — a header with a file extension (`UrlShortener.py:`). The physical location a Component's code lives in, resolved directly from the folder chain above it plus its own name — no separate discovery step or manifest, ever.
- **Class** — a header, inside a file, whose own children are further headers (not bullets). A grouping, needed only when one file holds more than one such grouping (multiple classes sharing a file, or a flat module that happens to need one).
- **Named entry** — a header, inside a file or class, whose own children are `- ` bullets. The thing that gets a comment handle and maps to exactly one method or property. *Shape-inferred*, not keyword-driven: whichever kind of children a header has decides what it is.
- **Bullet** — one plain-English sentence, `- ` prefixed. Any number of bullets under one named entry all describe that entry together — no one-bullet-per-entry limit. A bare bullet sitting directly on a file or class (not under any entry) is a class/file-level bullet — see §4.
- **Reference** — a plain-English mention of another entry or Component's exact name inside a bullet (`uses CredentialHasher for password verification`). Not special syntax.
- **Hint** — optional freetext after a header's name, before its colon (`Printer.js class:`, `parse function:`). A header's real name is always its first word; a hint is everything after it. Not enforced, not tracked, not hashed, not a fixed vocabulary — the parser discards it the moment the name's extracted. It exists purely for whoever's reading the raw file, human or compiler, as a clarifying note — a hint states something explicitly that was already true, it never changes what a header is.

  Shape-inference (§1's Class/Named entry split) already resolves *tree* shape correctly on its own, but it can't distinguish one case that comes up constantly: a File whose direct entries are one implicit class's methods (the common single-class-per-file case, no separate Class node needed) produces the exact same tree shape as a File whose direct entries are a flat module of unrelated standalone functions. The hint convention exists specifically to close that one gap:
  - A **File** header gets a `class` hint when its direct entries are one implicit class's methods/fields with no separate Class node — e.g. `Printer.js class:`, `CodeGenerator.py class:`. It gets no hint when its direct entries are a flat module of standalone functions with no implied class.
  - A genuine nested **Class** node (used only when a file holds more than one class) also gets a `class` hint, for the same at-a-glance legibility, even though shape-inference already resolves it correctly on its own — e.g. `NotesStore class:` inside a `notes.py:` that also holds `NotesValidator class:`.
  - A **named entry** gets a `function` hint only when it's a genuinely standalone function — sitting directly under a File that has no implied single class (a true flat-function module) — e.g. `parse function:`, `formatCurrency function:`. An entry that's a method, whether under an implicit single-class File or an explicit Class node, gets no hint; its home already says what it is.
  - A state/data-shape entry (mutable state's fields, e.g. `gameState`, `_code_to_url`) gets no hint either way — it's neither a class nor a function.

  Applied consistently once a file's own shape (implicit class, flat functions, or a mix) is judged — not added ad hoc where clarity seemed to matter.

### 1a. Scope: no entry for pure constant data

A file or entry with no behavior at all — a static lookup table, a seed/config array, literal values nothing computes from — is not described in llmlang, not even minimally. Prose is a poor format for literal data, and nothing about reconstruction needs it: another bullet that depends on the constant can just name it (`uses colorCodes to look up the display color`, per the Reference convention in §1) without the constant needing its own entry to reference. The line: **state shape** (what fields a piece of mutable state tracks and what they mean, e.g. `gameState`) is architecturally meaningful and stays in llmlang like any other data entry; **literal seed/constant values** (the specific hex codes, the specific rows of a static table) are not, and don't.

## 2. Formatting rules

- Indentation is exactly one tab per nesting level. No spaces.
- Every line is a header (ends in `:`), a bullet (`- ` prefixed), or `@policy:`.
- `@policy:` is the *only* reserved word, valid at root, folder, file, or class scope. Everything else is shape-inferred (§1).
- A header with a `.` in its name is a file (extension = everything after the last `.`); folders may contain folders or files, nothing else.
- Class vs. named entry is decided by what shows up first among a header's *header* children, not its first child overall — a class may legitimately open with a class-level bullet before its first named entry.
- A header's name is its first word; anything after it up to the colon is an optional Hint (§1), discarded once the name's extracted.

## 3. Structure grammar (informal)

```
llmlang  := (Policy | Folder | File)*
Folder   := Name Hint? ":" NEWLINE (Policy | Folder | File)*
File     := Name "." Ext Hint? ":" NEWLINE (Policy | Bullet | Class | Entry)*
Class    := Name Hint? ":" NEWLINE (Policy | Bullet | Entry)*
Entry    := Name Hint? ":" NEWLINE Bullet+
Policy   := "@policy:" NEWLINE Bullet+
Bullet   := "- " Sentence NEWLINE
```

## 4. "should" bullets — tests, without a reserved category

There is no `tests:` keyword. A bullet phrased `"should ..."` is read by the compiler as a test to build — a pure prose convention, invisible to the parser, which treats it exactly like any other bullet.

- Nested under the entry it tests (the common case): folds into that entry's own hash for free, zero extra tracking.
- A bare bullet on the file/class node itself, for a guarantee that spans *more than one* entry (e.g. a round-trip: create it, then look it up): tracked with its own `text_hash` (no `code_hash` — it has no single entry's code to attach to), and flagged for review whenever *any* entry it transitively depends on changes, for any reason. This is the one deliberate exception to "tests are free" — it exists specifically because folding a cross-entry guarantee into just one of the entries it actually depends on would silently lose invalidation when a *different* entry changes.

## 4a. "?" bullets — flagging suspected bugs, without deciding to fix them

A bullet prefixed `- ? ` states something the code genuinely does that looks unintentional — a real behavior, described faithfully (the concept doc §5's "describe, don't decide" applies here too), just flagged for a human to look at rather than silently corrected or silently left unremarkable. Same treatment as `should`: a pure prose convention, not parsed, not enforced, scannable at a glance the way a paragraph buried mid-bullet isn't.

Non-functional/performance claims follow a hard rule regardless of where they live: only valid if quantified enough to become an actual assertion ("responds within 200ms for lists under 10k"). "Should feel fast" is not valid llmlang.

## 4b. Inputs/outputs — bookend bullets, by convention

Where there's something to say, two separate single-purpose bullets frame the entry: an "accepts X" bullet as the *first* bullet, and a "returns Y" bullet as the *last* — the behavioral bullets sit between them. Either half is omitted when there's nothing to say — a function with no parameters gets no accepts bullet, a function with no return value gets no returns bullet, and a void no-arg function gets neither. Constructors are a special case: what they're constructed *from* matters and gets an accepts bullet ("accepts a name, size, width, and value"), but what they return is definitionally the new instance, which carries no information worth stating — a constructor never gets a returns bullet.

Never state the return value twice. If a regular behavioral bullet already says what's returned — most often because it already starts with "returns" itself ("returns whether the roll's original size is zero or less") — that bullet already *is* the closing returns bullet; it does not get a second, more generic "returns Y" bullet stacked next to it restating the same fact in vaguer words. Only add a standalone returns bullet when no existing bullet already states the return value explicitly. This makes the returns half of the convention closer to "make sure the return value is stated exactly once, and that whichever bullet does it sits last" than "always append a bullet."

## 5. Single-sourcing discipline

A behavior is described in exactly one named entry. A second entry that needs it does not restate it — it References the owning entry by name. Not automated: near-duplicate bullets with no Reference between them is a defect caught in **human/AI review**, catchable specifically because llmlang stays terse enough that duplication is visible at a glance — the same duplication invisible across thousands of lines of real code becomes obvious as two similar bullets sitting near each other.

## 6. Completeness — enough detail to reconstruct, not a summary

Bullets must fully specify the *behavior* they describe — exact thresholds, formulas, timing values, and edge-case outcomes — not a high-level gist a reader would need to check the code to fill in. The target is **behavioral** reconstruction: regenerating code from llmlang alone should produce something that behaves identically when tested, even though the exact code (naming, style, structure) is still expected to vary between compiles — the concept doc §3.1's non-determinism is fully still in play, this is about the spec being complete, not the output being deterministic.

This does not reopen the "no control flow, no algorithms" boundary from the concept doc §1. The distinction is **declarative vs. procedural**, not **detailed vs. vague**: describe *what must be true* — a rule, a constraint, an outcome — never *the steps to compute it*. "Never adds more mass in one tick than the printer's speed, the filament remaining, or the part's remaining unprinted mass" is a complete, precise rule a compiler can satisfy however it wants (a `min()` call, three sequential clamps, whatever) — it is not pseudocode, and it is not vague either. A bullet that only gestures at the gist ("adds mass at the printer's speed") isn't detailed vs. undetailed so much as *incomplete* — it's silently missing a real constraint.

Completeness and "should" bullets are related but not the same move. When a human and the compiler are actively deciding what's worth guaranteeing — greenfield authoring, or reviewing a proposed addition (the concept doc §3.2) — pairing a precise rule with a "should" bullet that checks it is the right instinct, since someone is there to approve that it's actually worth asserting as a permanent guarantee. During extraction specifically (the concept doc §5, and the onboarding methodology it points to), that approval hasn't happened yet: a rule gets written completely as a regular bullet and verified true against the real code, but does not become a "should" bullet unless a test for it already existed in the source. Asserting a new guarantee is a decision, not a description, and extraction only describes.

## 7. Worked example

```
Backend:
	@policy:
		- failures are handled gracefully and never crash the app

	UrlShortener.py class:
		create_short_code:
			- accepts a long URL
			- creates a unique short code for a given long URL
			- uses CodeGenerator to generate the code
			- generated codes must be unique per URL
			- should return the same code when called twice with the same URL
			- returns the short code

		get_url:
			- accepts a short code
			- looks up the original URL for a given short code
			- should return not found for an unknown short code
			- returns the original URL

		_code_to_url:
			- stores a mapping of short code to original URL

		- should return the original URL for a code that was previously created

	CodeGenerator.py class:
		generate:
			- generates a random 6-character alphanumeric code
			- returns the generated code

Frontend:
	ShortenerUI.html:
		form:
			- shows a text input for a long URL and a submit button

		shortenUrl function:
			- accepts the long URL
			- uses UrlShortener to create a short code when submitted
			- returns the short code

		renderShortUrl function:
			- accepts the short code
			- displays the resulting short URL as a clickable link to the original URL
```

## 8. Layout convention

Folder-per-Domain, file-per-Component is inherited directly from the llmlang tree — a file's own header carries its extension, and the folder chain above it carries its path, so `Backend/UrlShortener.py:` resolves to exactly that path with zero manifest and zero discovery step. This is a hard requirement for native (non-onboarded) code — see the concept doc §5 for what happens when it doesn't hold.

# llmlang — Concept & Design (v0.2)

Status: prototype tooling, built and working. Three example projects verified end-to-end: `shortener.llm` (greenfield), `compiler.llm` (self-hosted — the compiler's own tooling described in its own language), `notes.llm` (onboarded legacy code). Sections marked **OPEN** are genuinely unresolved. For the concrete syntax and writing conventions, see the [format spec](llmlang-format.md).

## 1. What llmlang is

llmlang is a plain-text architecture-description language that sits between a prose spec and real code. A human (or human+AI) describes a system as files, classes, and named entries — their responsibilities, dependencies, and expected behavior — at the level an engineer would use to review a design, not implement one. An LLM "compiles" llmlang into working code. llmlang, not the generated code, is the primary artifact of human review and PR discussion.

Explicitly not in scope for llmlang itself: function signatures, control flow, algorithms — anything at the logic level. That stays the compiler's (the LLM's) discretion, bounded by the mechanisms in §3.

**The compiler isn't software to build — it's an LLM, prompted correctly.** Given a dirty entry's bullets and the surrounding context, an LLM already writes the code; that's exactly what happened by hand, in conversation, for every example in this repo. Everything described in §4 (the lockfile/tooling) verifies *consistency* between already-written llmlang and already-written code, and, via `--finalize` (§4.4), guarantees nothing gets silently skipped while an LLM works through a batch of changes — but it doesn't invoke an LLM itself. See §7.

## 2. Precedents (context, not a mechanism to copy)

- **Interface/contract-first design** (IDL, Protobuf, Thrift, OpenAPI) — precedent for "declare the interface, generate an implementation."
- **Gherkin/BDD** — precedent for plain-text test cases compiling into executable tests. Gherkin still needs hand-written glue code; llmlang's compiler writes the whole test body.
- **C4 model** (c4model.com, Simon Brown) — precedent for the abstraction level (Container/Component, stopping short of code). No compile mechanism of its own — purely descriptive.
- **UML round-trip engineering** — precedent for forward-generating code from a model and reverse-generating a model from code, kept in sync. Also the precedent for cascading invalidation.
- **npm's `package-lock.json`** — precedent for the lockfile's actual shape: a machine-owned snapshot, versioned separately from the human-edited source, with an integrity hash whose job is "detect corruption," not "track intent."
- **AOP** (AspectJ) — precedent for `@policy:` (§3.3): declare a cross-cutting rule once, apply it broadly. llmlang deliberately avoids AOP's actual historical failure (runtime weaving making code unreadable in isolation) by inlining a policy's effect into literal generated source at compile time instead.
- Explicitly ruled out as not-quite-this: Tessl/spec-driven dev, Sean Grove's "specs are the new code," GitHub spec-kit, AWS Kiro (its staged review pipeline is the precedent for the draft-then-review flow in §5), "vibe coding," 1980s Program Design Language / 4GLs.

## 3. Compilation model

### 3.1 Non-determinism is accepted, not fought

The compiler does not need to be deterministic. What has to stay bounded is *conformance to llmlang*, not *identity of output*.

**Structural gate**: every named entry's code must be locatable via its comment handle (§4.1) — no invented, untraceable public surface. Near-identical logic across two entries with no Reference between them signals the spec under-specified something; fix llmlang, not just the code ([the format spec](llmlang-format.md) §5). This is a human/AI review discipline, not an automated check.

**Behavioral gate**: generated code must pass whatever tests were compiled from "should" bullets ([the format spec](llmlang-format.md) §4).

Method/function *bodies* are the only thing with zero llmlang trace — the intended scope of full compiler discretion.

### 3.2 The mapping requirement resolves the discretion boundary

A compile-time decision not specified in llmlang (timeout handling, caching strategy) is not left to silent judgment: if it would produce something needing its own named entry to stay traceable, the compiler must propose that entry to llmlang and get sign-off before finalizing code. This is the same mechanism as two other cases:

- **Bug fixes** — a report becomes a proposed "should" bullet, not a direct patch. The fix and the spec change land together, reviewed together — no hotfix path that bypasses spec review.
- **Deduplication** — noticing two entries should share logic is a proposed llmlang restructure (extract a shared entry, add a Reference), not a silent code refactor.

**One rule, three triggers**: whenever compile hits a gap between what llmlang says and what the code needs to do, the compiler proposes an addition and waits. This is what makes llmlang bidirectional — the AI is a co-author of the spec, not just a consumer of it.

**OPEN / soft edge**: every code branch is technically an unmapped decision. The compiler still needs judgment about which ones rise to "a human would care" vs. pure plumbing — an accepted non-determinism tradeoff, not solved by a separate rule.

### 3.3 Policy — cross-cutting concerns, AOP-shaped without AOP's failure

`@policy:` is valid at root, folder, file, or class scope, and cascades to everything nested beneath wherever it's declared:

```
Backend:
	@policy:
		- every call is logged using Logger
```

The compiler inlines a policy's effect directly into each generated entry's literal source at compile time — no runtime weaving, no decorator indirection. Generated code stays fully self-contained and readable; the "invisibility" AOP was criticized for exists only one layer up, at the spec (checking the enclosing `@policy:` block to know *why* code looks a certain way), never at the code layer (what you read is what runs). Repeated boilerplate across entries from a shared policy is expected, not a duplication smell — the review discipline in [the format spec](llmlang-format.md) §5 needs to treat policy-explained repetition differently from unexplained repetition.

## 4. Lockfile and traceability

### 4.1 Comment handles

Every named entry has one canonical name: its full llmlang path, built from the folder chain, file name without extension, optional class header, and entry identifier. Source comments use that exact canonical name in the handle.

Every named entry gets exactly one source comment: the entry's parenthesized summary, rendered in the source language's comment syntax, immediately followed by its canonical-name handle:

```python
# creates a unique short code for a given long URL [llm:Backend.UrlShortener.create_short_code]
def create_short_code(self, url: str) -> str:
    ...
```

The canonical name is stable across reordering, unlike an earlier index-based scheme (`function0`, `function1`) that silently changed identity when bullets were reordered.

**Deliberately not heuristic.** A named entry's code is everything from its handle to the *next* handle in the file, or EOF — nothing inferred from indentation or blank lines. This can include unrelated code sitting between two handles (known, accepted coarseness — see below), but what it includes never depends on how surrounding code happens to be formatted. An indentation/blank-line heuristic was tried and explicitly rejected: its correctness would silently depend on formatting, which conflicts with the project's bias toward mechanisms that fail loud over ones that can be silently wrong.

The entry identifier is expected to match the real code identifier (soft convention, guides the compiler) but this is never tooling-enforced — enforcing it would require language-specific identifier rules, which conflicts with staying language-agnostic. Only the canonical-name handle is authoritative.

### 4.2 The lockfile

A separate, machine-owned file (`*.llmlock`) — never referenced from source comments, and llmlang source needs no version marker of its own (it's always parsed fresh by the current grammar; the lockfile is what gets compared across time, so that's where version drift needs detecting). Two kinds of hash, different in purpose:

- **`text_hash`** (every entry, every policy, every class-level bullet group) — hash of the llmlang text. Mismatch is reported as `SPEC_DIVERGED` — the spec side moved (its own bullets changed, it's brand new, or an upstream policy covering it changed); safe default is to update the code to match.
- **`code_hash`** (named entries only) — hash of the code the handle locates. Mismatch is reported as `CODE_DIVERGED` — the code side moved with no corresponding spec change to explain it; *not* safe to blindly regenerate, investigate first, since this usually means something broke rather than an intentional change nobody documented. This is *not* a drift-vs-hand-edit reconciliation mechanism (llmlang is explicitly the layer humans edit, hand-edited code is out of scope) — it's a plain integrity checksum, same job as npm's `package-lock.json` `integrity` field.

Two version fields, both lockfile-only:

- `lockfile_schema_version` (int) — hard gate, checked first, refuses with "rebuild it" on mismatch.
- `ruleset_version` (string) — soft cascade, reusing the exact root-`@policy:` cascade mechanism (a ruleset change is structurally a root-scope policy change) — flags every entry for review rather than refusing outright, since "all entries locked to one ruleset together" is a single field, not per-entry.

### 4.3 Cascades — three, composing through each other

1. **Policy → entries**: a changed `@policy:` flags every entry within its scope `SPEC_DIVERGED`, even if the entry's own hashes still match.
2. **Entries → class-level "should" bullets**: a cross-entry bullet is flagged whenever any entry it depends on was flagged, for any reason ([the format spec](llmlang-format.md) §4).
3. **Any code item → its sibling entries generally**: verified to chain correctly — a policy change was shown to cascade through entries and *then* through to a class-level bullet depending on those entries, in one live test.

A hash mismatch is not a verdict, it's a prompt: "go look at what changed in this region." A false positive costs one quick review, not a wrong result — this is why the deterministic (non-heuristic), fairly coarse handle-region rule in §4.1 is acceptable rather than a problem to solve more precisely.

### 4.4 Finalize — a guarded rebuild that can't silently skip an entry

`Compiler/LockfileBuilder.py` has two entry points, deliberately different in what they trust. `build()` (plain `build.py <file>.llm`, no flags) is unguarded: it hashes whatever code currently sits at each handle and stamps it as correct, with no comparison to any prior state and no notion of dispositions at all. That's fine for bootstrapping a brand new lockfile, or for a human directly supervising their own paired edit — but it's a real gap for a multi-entry LLM-driven pass: if 4 of 5 flagged entries get fixed and one is forgotten, `build()` will happily hash the forgotten entry's *stale* code alongside its *new* bullets and record that pair as consistent, and the next `--check` reports clean even though that entry no longer matches its spec.

`finalize()` (`build.py <file>.llm --finalize`) closes that gap. It reads and updates `<stem>.llmchanges.json` — a real, git-tracked sibling file next to the `.llm` and `.llmlock`. A fresh entry is authored the same way the `.llm` file itself is (by hand or by an LLM, reviewed via its own git diff) — just `{tracking_key: "free text describing what changed, or why nothing needed to"}`. There's no fixed vocabulary for the text (same "not a fixed vocabulary" stance as Hints), and the tool never writes or edits the text itself.

Before writing anything, `finalize()` compares the current `.llm`/code against the *existing* lockfile to find what's currently flagged, then refuses outright — writing neither file — unless every flagged key has a non-empty entry in the changes file. Once that gate passes, both the new lockfile and the changes file are computed *purely* from the current `.llm` text, the current code, the current policies, and the current changes file — nothing is copied forward from the lockfile's own prior content. A fresh (bare-string) changes-file entry gets upgraded in place into `{disposition, for_spec_hash, for_code_hash}`, bound to the exact hashes it was just accepted against. `for_spec_hash` isn't just the entry's own text hashed alone — it folds in the text of every `@policy:` currently covering that entry too, so a disposition goes stale if *either* the entry's own bullets change *or* an applicable policy does (when nothing covers the entry, this reduces to exactly its own text hash). An already-stamped entry is kept only if both hashes still match the entry's *current* state — otherwise it's dropped as stale, along with any entry whose key no longer exists in the `.llm` tree at all (orphaned). Since "stale" and "the entry moved on" are the same signal, an entry that changes again without ever going through `--finalize` — including a policy above it changing — loses its old disposition automatically rather than having it silently reused against unrelated new state; an entry that never changes keeps its disposition indefinitely, re-affirmed on every successful run, with no separate cleanup step or accumulating changelog needed.

This guarantees **coverage** (nothing gets silently skipped), not **correctness** (whether a disposition is actually true). Those are different problems: a hash — or a human-readable disposition string — can prove an entry was addressed, but neither can prove it was addressed *correctly*, since an LLM could fabricate a disposition as easily as it could write wrong code. Correctness stays exactly where it's always been in this design: a human reviewing the diff. What finalize adds is that an omission can no longer hide — a forgotten entry shows up as a specific, named gap in the changes file, not silent drift discovered later.

## 5. Onboarding an existing codebase

Concrete step-by-step methodology (extraction and ongoing sync, both directions of drift) lives in [onboarding-spec.md](onboarding-spec.md). This section covers the design rationale; that document is the actual procedure to follow.

Reverse compilation (code → llmlang) is mostly an LLM/text task — reading code and writing prose — plus two mechanical touchpoints already covered by the tooling above: inserting handles, and round-trip verification (build the lockfile against the freshly annotated code; if there's a pre-existing test suite, it must still pass unchanged).

**Rejected approach**: a `<stem>.filemap.json` override file letting onboarded components live wherever their code already is, bypassing the folder-per-Domain/file-per-Component convention. Rejected outright as the same silent-indirection pattern the lockfile's own design exists to avoid — "if the code can't be mapped, raise it to the human," matching every other missing/corrupt case, not a side-channel around it. A component that can't be found now produces a clear error naming exactly what to rename, rather than either crashing or silently routing around the mismatch.

**Actual approach**: name Domains/Components to match the code's real existing structure — the same zero-manifest convention just resolves it once names match reality. The concrete procedure lives in the [onboarding methodology](onboarding-spec.md) (step 8); this is the design reasoning behind it, not a second copy of the steps.

**Bonus use case — legacy audit**: reverse-extraction faithfully encoding existing duplication into llmlang isn't a problem to avoid, it's the value — duplication invisible across thousands of lines of code becomes obvious once compressed into a few nearby bullets ([the format spec](llmlang-format.md) §5). Gives a concrete refactor path: extract raw → human consolidates duplicates into single-sourced entries with References → forward compile → verify against old behavior via round-trip.

## 6. Review model

Two-layer trust:

1. **Human review of the llmlang diff** — the primary PR artifact, the level engineers think and communicate at.
2. **Automated conformance** (§3.1) — structural + behavioral gates catch what a human would normally catch reading code, since generated code isn't the primary review surface by default.

**OPEN**: no mitigation yet for code that's behaviorally correct (passes tests, matches llmlang) but has a real problem the architecture-level spec had no way to describe (perf, security) that hasn't surfaced as a bug report yet.

## 7. Implementation status

Built and verified end-to-end (in [`compiler/`](compiler/)):

- `Compiler/Parser.py` — the grammar in [the format spec](llmlang-format.md), stack-based (item depth varies by context, so a fixed-depth parser doesn't work).
- `Compiler/Extractor.py` — handle-based code lookup (§4.1).
- `Compiler/LockfileBuilder.py` / `LockfileChecker.py` — the lockfile, all three cascades in §4, and the guarded `--finalize` path (§4.4).
- `build.py` — generic CLI (`build.py <file>.llm [--check | --finalize]`), works on any llmlang file, self-hosts (compiles its own `compiler.llm`).

Compiling (llmlang → code) still isn't automated, but that's not missing software — it's an LLM given the format spec, this doc, and the target `.llm` file, writing code that satisfies every bullet. That's exactly what happened, by hand, for every example in this repo, and it doesn't need a separate portable instructions document restating rules the format spec and this doc already state in full — that would just be the duplication §3.5's single-sourcing discipline exists to avoid. What `--finalize` actually adds is narrower and more useful: a mechanical guarantee that whoever does the compiling, human or LLM, can't silently skip an entry while doing it.

## 8. Summary of open questions

- §3.2 — no fixed rule for which decisions are "significant enough" to require a proposal; an accepted judgment call.
- §6 — no mitigation for correct-but-flawed generated code that hasn't triggered a bug report yet.
- §4.4 — `--finalize` guarantees coverage (nothing silently skipped), not correctness (whether a disposition is true); a fabricated disposition is still possible, and still ultimately a human-review problem, same as generated code always has been.
- Not yet touched: what compile-time LLM context looks like in practice (how much of the rest of the codebase a given entry's compile step sees), what language(s) beyond Python/HTML/JS the tooling has been proven against, the split-a-method direction of the 1:1 rule (only the merge-bullets direction has come up in practice so far).

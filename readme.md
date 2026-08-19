# llmlang — Concept & Design (v0.2)

Status: prototype tooling built and working (`C:\Users\altbi\llmlang\`). Three example projects verified end-to-end: `shortener.llm` (greenfield), `compiler.llm` (self-hosted — the compiler's own tooling described in its own language), `notes.llm` (onboarded legacy code). Sections marked **OPEN** are genuinely unresolved. For the concrete syntax and writing conventions, see the format spec (`llmlang-format.md`).

## 1. What llmlang is

llmlang is a plain-text architecture-description language that sits between a prose spec and real code. A human (or human+AI) describes a system as files, classes, and named entries — their responsibilities, dependencies, and expected behavior — at the level an engineer would use to review a design, not implement one. An LLM "compiles" llmlang into working code. llmlang, not the generated code, is the primary artifact of human review and PR discussion.

Explicitly not in scope for llmlang itself: function signatures, control flow, algorithms — anything at the logic level. That stays the compiler's (the LLM's) discretion, bounded by the mechanisms in §3.

**Not yet built**: an actual llmlang → code generator. Everything described in §4 (the lockfile/tooling) verifies *consistency* between already-written llmlang and already-written code — it doesn't write code from llmlang on its own. In every example so far, the LLM (a person, in conversation) played the compiler role by hand. See §7.

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

**Structural gate**: every named entry's code must be locatable via its comment handle (§4.1) — no invented, untraceable public surface. Near-identical logic across two entries with no Reference between them signals the spec under-specified something; fix llmlang, not just the code (the format spec §5). This is a human/AI review discipline, not an automated check.

**Behavioral gate**: generated code must pass whatever tests were compiled from "should" bullets (the format spec §4).

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

The compiler inlines a policy's effect directly into each generated entry's literal source at compile time — no runtime weaving, no decorator indirection. Generated code stays fully self-contained and readable; the "invisibility" AOP was criticized for exists only one layer up, at the spec (checking the enclosing `@policy:` block to know *why* code looks a certain way), never at the code layer (what you read is what runs). Repeated boilerplate across entries from a shared policy is expected, not a duplication smell — the review discipline in the format spec §5 needs to treat policy-explained repetition differently from unexplained repetition.

## 4. Lockfile and traceability

### 4.1 Comment handles

Every named entry gets exactly one comment, human-readable text immediately followed by a machine handle:

```python
# creates a unique short code for a given long URL, using CodeGenerator to generate the code [llm:create_short_code]
def create_short_code(self, url: str) -> str:
    ...
```

The handle key is the entry's own name — stable across reordering, unlike an earlier index-based scheme (`function0`, `function1`) that silently changed identity when bullets were reordered. When a file holds multiple classes, the key is qualified by class (`[llm:NotesValidator.is_valid]`); a file with one implicit grouping uses the bare name.

**Deliberately not heuristic.** A named entry's code is everything from its handle to the *next* handle in the file, or EOF — nothing inferred from indentation or blank lines. This can include unrelated code sitting between two handles (known, accepted coarseness — see below), but what it includes never depends on how surrounding code happens to be formatted. An indentation/blank-line heuristic was tried and explicitly rejected: its correctness would silently depend on formatting, which conflicts with the project's bias toward mechanisms that fail loud over ones that can be silently wrong.

The name is expected to match the real code identifier (soft convention, guides the compiler) but this is never tooling-enforced — enforcing it would require language-specific identifier rules, which conflicts with staying language-agnostic. Only the handle is authoritative.

### 4.2 The lockfile

A separate, machine-owned file (`*.llmlock`) — never referenced from source comments, and llmlang source needs no version marker of its own (it's always parsed fresh by the current grammar; the lockfile is what gets compared across time, so that's where version drift needs detecting). Two kinds of hash, different in purpose:

- **`text_hash`** (every entry, every policy, every class-level bullet group) — hash of the llmlang text. Mismatch means the spec changed; recompile.
- **`code_hash`** (named entries only) — hash of the code the handle locates. Mismatch means the code doesn't match what was last produced — missing or corrupt, just regenerate. This is *not* a drift-vs-hand-edit reconciliation mechanism (llmlang is explicitly the layer humans edit, hand-edited code is out of scope) — it's a plain integrity checksum, same job as npm's `package-lock.json` `integrity` field.

Two version fields, both lockfile-only:

- `lockfile_schema_version` (int) — hard gate, checked first, refuses with "rebuild it" on mismatch.
- `ruleset_version` (string) — soft cascade, reusing the exact root-`@policy:` cascade mechanism (a ruleset change is structurally a root-scope policy change) — flags every entry for review rather than refusing outright, since "all entries locked to one ruleset together" is a single field, not per-entry.

### 4.3 Cascades — three, composing through each other

1. **Policy → entries**: a changed `@policy:` flags every entry within its scope `NEEDS REVIEW`, even if the entry's own hashes still match.
2. **Entries → class-level "should" bullets**: a cross-entry bullet is flagged whenever any entry it depends on was flagged, for any reason (the format spec §4).
3. **Any code item → its sibling entries generally**: verified to chain correctly — a policy change was shown to cascade through entries and *then* through to a class-level bullet depending on those entries, in one live test.

A hash mismatch is not a verdict, it's a prompt: "go look at what changed in this region." A false positive costs one quick review, not a wrong result — this is why the deterministic (non-heuristic), fairly coarse handle-region rule in §4.1 is acceptable rather than a problem to solve more precisely.

## 5. Onboarding an existing codebase

Concrete step-by-step methodology (extraction and ongoing sync, both directions of drift): `C:\Users\altbi\llmlang\onboarding-spec.md`. This section covers the design rationale; that document is the actual procedure to follow.

Reverse compilation (code → llmlang) is mostly an LLM/text task — reading code and writing prose — plus two mechanical touchpoints already covered by the tooling above: inserting handles, and round-trip verification (build the lockfile against the freshly annotated code; if there's a pre-existing test suite, it must still pass unchanged).

**Rejected approach**: a `<stem>.filemap.json` override file letting onboarded components live wherever their code already is, bypassing the folder-per-Domain/file-per-Component convention. Rejected outright as the same silent-indirection pattern the lockfile's own design exists to avoid — "if the code can't be mapped, raise it to the human," matching every other missing/corrupt case, not a side-channel around it. A component that can't be found now produces a clear error naming exactly what to rename, rather than either crashing or silently routing around the mismatch.

**Actual approach**: name Domains/Components to match the code's real existing structure — the same zero-manifest convention just resolves it once names match reality. The concrete procedure lives in the onboarding methodology (step 8); this is the design reasoning behind it, not a second copy of the steps.

**Bonus use case — legacy audit**: reverse-extraction faithfully encoding existing duplication into llmlang isn't a problem to avoid, it's the value — duplication invisible across thousands of lines of code becomes obvious once compressed into a few nearby bullets (the format spec §5). Gives a concrete refactor path: extract raw → human consolidates duplicates into single-sourced entries with References → forward compile → verify against old behavior via round-trip.

## 6. Review model

Two-layer trust:

1. **Human review of the llmlang diff** — the primary PR artifact, the level engineers think and communicate at.
2. **Automated conformance** (§3.1) — structural + behavioral gates catch what a human would normally catch reading code, since generated code isn't the primary review surface by default.

**OPEN**: no mitigation yet for code that's behaviorally correct (passes tests, matches llmlang) but has a real problem the architecture-level spec had no way to describe (perf, security) that hasn't surfaced as a bug report yet.

## 7. Implementation status

Built and verified end-to-end (`C:\Users\altbi\llmlang\compiler\`):

- `Compiler/Parser.py` — the grammar in the format spec, stack-based (item depth varies by context, so a fixed-depth parser doesn't work).
- `Compiler/Extractor.py` — handle-based code lookup (§4.1).
- `Compiler/LockfileBuilder.py` / `LockfileChecker.py` — the lockfile and all three cascades in §4.
- `build.py` — generic CLI (`build.py <file>.llm [--check]`), works on any llmlang file, self-hosts (compiles its own `compiler.llm`).

**Not built**: the actual compiler — something that reads a dirty entry's bullets and *writes* code for it. Every example so far was hand-compiled: a person wrote the llmlang and the code together, then used the tooling above to verify they agree. There is no automated "take `LockfileChecker`'s DIRTY list and generate code for each entry" step, and no portable instructions document yet encoding the rules in §3 for an LLM to actually follow as a compiler (discussed as a productionization idea — a VSCode Chat Participant reading such a document was the sketched integration point, not yet drafted or built).

## 8. Summary of open questions

- §3.2 — no fixed rule for which decisions are "significant enough" to require a proposal; an accepted judgment call.
- §6 — no mitigation for correct-but-flawed generated code that hasn't triggered a bug report yet.
- §7 — the actual compiler (llmlang → code) and its instructions document don't exist yet; only the verification tooling does.
- Not yet touched: what compile-time LLM context looks like in practice (how much of the rest of the codebase a given entry's compile step sees), what language(s) beyond Python/HTML/JS the tooling has been proven against, the split-a-method direction of the 1:1 rule (only the merge-bullets direction has come up in practice so far).

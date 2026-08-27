# llmlang: Concept & Design (v0.2)

Status: prototype tooling, built and working. Three example projects verified end-to-end: `shortener.llm` (greenfield), `compiler.llm` (self-hosted, the compiler's own tooling described in its own language), `notes.llm` (onboarded legacy code). Sections marked **OPEN** are unresolved. For the concrete syntax and writing conventions, see the [format spec](llmlang-format.md).

## 1. What llmlang is

llmlang is a plain-text architecture-description language that sits between a prose spec and real code. A human (or human+AI) describes a system as files, classes, and named entries: their responsibilities, dependencies, and expected behavior, at the level an engineer would use to review a design, not implement one. An LLM "compiles" llmlang into working code. llmlang, not the generated code, is the primary artifact of human review and PR discussion.

Explicitly not in scope for llmlang itself: function signatures, control flow, algorithms, anything at the logic level. That stays the compiler's (the LLM's) discretion, bounded by the mechanisms in §2.

**The compiler isn't software to build, it's an LLM, prompted correctly.** Given a dirty entry's bullets and the surrounding context, an LLM already writes the code; that's exactly what happened by hand, in conversation, for every example in this repo. Everything described in §3 (the lockfile/tooling) verifies *consistency* between already-written llmlang and already-written code, and, via `finalize` (§3.4), guarantees nothing gets silently skipped while an LLM works through a batch of changes, but it doesn't invoke an LLM itself. See §6.

## 2. Compilation model

### 2.1 Non-determinism is accepted, not fought

The compiler does not need to be deterministic. What has to stay bounded is *conformance to llmlang*, not *identity of output*.

**Structural gate**: every named entry's code must be locatable via its comment handle (§3.1), no invented, untraceable public surface. Near-identical logic across two entries with no Reference between them signals the spec under-specified something; fix llmlang, not just the code ([the format spec](llmlang-format.md) §5). This is a human/AI review discipline, not an automated check.

**Behavioral gate**: generated code must pass whatever tests are represented by `~` bullets and linked test comments ([the format spec](llmlang-format.md) §4).

Method/function *bodies* are the only thing with zero llmlang trace, the intended scope of full compiler discretion.

### 2.2 The mapping requirement resolves the discretion boundary

A compile-time decision not specified in llmlang (timeout handling, caching strategy) is not left to silent judgment: if it would produce something needing its own named entry to stay traceable, the compiler must propose that entry to llmlang and get sign-off before finalizing code. This is the same mechanism as two other cases:

- **Bug fixes**: a report becomes a proposed behavior bullet plus, when covered by a test, a `~` bullet and linked test comment, not a direct patch. The fix and the spec change land together, reviewed together; no hotfix path that bypasses spec review.
- **Deduplication**: noticing two entries should share logic is a proposed llmlang restructure (extract a shared entry, add a Reference), not a silent code refactor.

**One rule, three triggers**: whenever compile hits a gap between what llmlang says and what the code needs to do, the compiler proposes an addition and waits. This is what makes llmlang bidirectional: the AI is a co-author of the spec, not just a consumer of it.

Every code branch is technically an unmapped decision, and the compiler still needs judgment about which ones rise to "a human would care" vs. pure plumbing. That's not a gap awaiting a fix; it's the accepted non-determinism tradeoff from §2.1, applied here specifically, and no separate rule is meant to close it.

### 2.3 Policy: cross-cutting concerns, inlined rather than woven in

`@policy:` is valid at root, folder, file, or class scope, and cascades to everything nested beneath wherever it's declared:

```
Backend:
	@policy:
		- every call is logged using Logger
```

The compiler inlines a policy's effect directly into each generated entry's literal source at compile time, no runtime weaving, no decorator indirection. Generated code stays fully self-contained and readable: knowing *why* code looks a certain way means checking the enclosing `@policy:` block, one layer up at the spec, but at the code layer what you read is what runs. Repeated boilerplate across entries from a shared policy is expected, not a duplication smell; the review discipline in [the format spec](llmlang-format.md) §5 needs to treat policy-explained repetition differently from unexplained repetition.

## 3. Lockfile and traceability

### 3.1 Comment handles

Every named entry has one canonical name: its full llmlang path, built from the folder chain, file name without extension, optional class header, and entry identifier. Source comments use that exact canonical name in the handle, stable across reordering.

Every named entry gets exactly one source comment: the entry's parenthesized summary, rendered in the source language's comment syntax, immediately followed by its canonical-name handle:

```python
# creates a unique short code for a given long URL [llm:Backend.UrlShortener.create_short_code]
def create_short_code(self, url: str) -> str:
    ...
```

**Deliberately not heuristic.** A named entry's code is everything from its handle to the *next* handle in the file, or EOF, nothing inferred from indentation or blank lines. This can include unrelated code sitting between two handles (known, accepted coarseness, see below), but what it includes never depends on how surrounding code happens to be formatted, since that would make correctness silently depend on formatting.

The entry identifier is expected to match the real code identifier (soft convention, guides the compiler) but this is never tooling-enforced; enforcing it would require language-specific identifier rules, which conflicts with staying language-agnostic. Only the canonical-name handle is authoritative.

### 3.2 The lockfile

A separate, machine-owned file (`*.llmlock`), never referenced from source comments. llmlang source needs no version marker of its own: it's always parsed fresh by the current grammar, and the lockfile is what gets compared across time, so that's where version drift needs detecting. Two kinds of hash, different in purpose:

- **`text_hash`** (every entry, every policy, every class-level bullet group): hash of the llmlang text. Mismatch is reported as `SPEC_DIVERGED`, the spec side moved (its own bullets changed, it's brand new, or an upstream policy covering it changed); safe default is to update the code to match.
- **`code_hash`** (named entries only): hash of the code the handle locates. Mismatch is reported as `CODE_DIVERGED`, the code side moved with no corresponding spec change to explain it; not safe to blindly regenerate, investigate first, since this usually means something broke rather than an intentional change nobody documented. This is not a drift-vs-hand-edit reconciliation mechanism (llmlang is explicitly the layer humans edit, hand-edited code is out of scope); it's a plain integrity checksum.
- **`test_traces`** (`~` bullets only): records the exact test explanation text, relative source path, and backing test code hash for every linked `llm-test` comment. Mismatch is reported separately from entry drift: `TEST_LINK_MISSING` for a `~` bullet with no source comment, `TEST_TRACE_STALE` for a source comment with no `~` bullet, `TEST_TRACE_DIVERGED` when the link moved or is new relative to the lockfile, and `TEST_CODE_DIVERGED` when the linked test block changed. The trace uses paths and hashes rather than line numbers or source snippets, so moving code within a file only matters if the backing test block's hash changes.

Two version fields, both lockfile-only:

- `lockfile_schema_version` (int): hard gate, checked first, refuses with "rebuild it" on mismatch.
- `ruleset_version` (string): soft cascade, reusing the exact root-`@policy:` cascade mechanism (a ruleset change is structurally a root-scope policy change), flags every entry for review rather than refusing outright, since "all entries locked to one ruleset together" is a single field, not per-entry.

### 3.3 Cascades: three, composing through each other

1. **Policy → entries**: a changed `@policy:` flags every entry within its scope `SPEC_DIVERGED`, even if the entry's own hashes still match.
2. **Entries → class/file-level bullets**: a cross-entry bullet is flagged whenever any entry it depends on was flagged, for any reason ([the format spec](llmlang-format.md) §1).
3. **Any code item → its sibling entries generally**: verified to chain correctly; a policy change was shown to cascade through entries and *then* through to a class-level bullet depending on those entries, in one live test.

A hash mismatch is not a verdict, it's a prompt: "go look at what changed in this region." A false positive costs one quick review, not a wrong result. That's why the deterministic (non-heuristic), fairly coarse handle-region rule in §3.1 is acceptable rather than a problem to solve more precisely.

### 3.4 Finalize: a guarded rebuild that can't silently skip an entry

`llmlang/lockfile_builder.py` has two entry points, deliberately different in what they trust. `build()` (`llmlang build <file>.llm`) is unguarded: it hashes whatever code currently sits at each handle and stamps it as correct, with no comparison to any prior state and no notion of dispositions at all. That's fine for bootstrapping a brand new lockfile, or for a human directly supervising their own paired edit, but it's a real gap for a multi-entry LLM-driven pass: if 4 of 5 flagged entries get fixed and one is forgotten, `build()` will happily hash the forgotten entry's *stale* code alongside its *new* bullets and record that pair as consistent, and the next `check` reports clean even though that entry no longer matches its spec.

`finalize()` (`llmlang finalize <file>.llm`) closes that gap. It reads and updates `<stem>.llmchanges.json`, a real, git-tracked sibling file next to the `.llm` and `.llmlock`. A fresh entry is authored the same way the `.llm` file itself is (by hand or by an LLM, reviewed via its own git diff): just `{tracking_key: "free text describing what changed, or why nothing needed to"}`. There's no fixed vocabulary for the text (same "not a fixed vocabulary" stance as Hints), and the tool never writes or edits the text itself.

Before writing anything, `finalize()` compares the current `.llm`/code against the *existing* lockfile to find what's currently flagged, then refuses outright, writing neither file, unless every flagged key has a non-empty entry in the changes file. Once that gate passes, both the new lockfile and the changes file are computed *purely* from the current `.llm` text, the current code, the current policies, and the current changes file; nothing is copied forward from the lockfile's own prior content. A fresh (bare-string) changes-file entry gets upgraded in place into `{disposition, for_spec_hash, for_code_hash}`, bound to the exact hashes it was just accepted against. `for_spec_hash` isn't just the entry's own text hashed alone; it folds in the text of every `@policy:` currently covering that entry too, so a disposition goes stale if *either* the entry's own bullets change *or* an applicable policy does (when nothing covers the entry, this reduces to exactly its own text hash). An already-stamped entry is kept only if both hashes still match the entry's *current* state, otherwise it's dropped as stale, along with any entry whose key no longer exists in the `.llm` tree at all (orphaned). Since "stale" and "the entry moved on" are the same signal, an entry that changes again without ever going through `finalize`, including a policy above it changing, loses its old disposition automatically rather than having it silently reused against unrelated new state; an entry that never changes keeps its disposition indefinitely, re-affirmed on every successful run, with no separate cleanup step or accumulating changelog needed.

This guarantees **coverage** (nothing gets silently skipped), not **correctness** (whether a disposition is true). Those are different problems: a hash, or a human-readable disposition string, can prove an entry was addressed, but neither can prove it was addressed *correctly*, since an LLM could fabricate a disposition as easily as it could write wrong code. Correctness stays exactly where it's always been in this design: a human reviewing the diff. What finalize adds is that an omission can no longer hide; a forgotten entry shows up as a specific, named gap in the changes file, not silent drift discovered later.

## 4. Onboarding an existing codebase

Concrete step-by-step methodology (extraction and ongoing sync, both directions of drift) lives in [onboarding-spec.md](onboarding-spec.md). This section covers the design rationale; that document is the actual procedure to follow.

Reverse compilation (code → llmlang) is mostly an LLM/text task, reading code and writing prose, plus two mechanical touchpoints already covered by the tooling above: inserting handles, and round-trip verification (build the lockfile against the freshly annotated code; if there's a pre-existing test suite, it must still pass unchanged).

**Layout convention**: name Domains/Components to match the code's real existing structure. The zero-manifest convention (a file's own header carries its extension and path, no separate mapping file needed) resolves cleanly once names match reality. When a component can't be located this way, that produces a clear, actionable error naming exactly what to rename, rather than silently routing around the mismatch or crashing, the same "raise it to the human" pattern every other missing/corrupt case in this design already follows. The concrete procedure lives in the [onboarding methodology](onboarding-spec.md) (step 8); this is the design reasoning behind it, not a second copy of the steps.

**Bonus use case (legacy audit)**: reverse-extraction faithfully encoding existing duplication into llmlang isn't a problem to avoid, it's the value. Duplication invisible across thousands of lines of code becomes obvious once compressed into a few nearby bullets ([the format spec](llmlang-format.md) §5). Gives a concrete refactor path: extract raw, human consolidates duplicates into single-sourced entries with References, forward compile, verify against old behavior via round-trip.

## 5. Review model

Two-layer trust:

1. **Human review of the llmlang diff**: the primary PR artifact, the level engineers think and communicate at.
2. **Automated conformance** (§2.1): structural + behavioral gates catch what a human would normally catch reading code, since generated code isn't the primary review surface by default.

**Partially open**: `@policy:` (§2.3) already covers any non-functional constraint someone thought to write down in advance, security or performance requirements included, since a policy is reviewed and inlined into every entry it covers the same as any other spec content. What's still unaddressed is a concern nobody thought to flag in the first place: code that's behaviorally correct (passes tests, matches llmlang) but has a real problem the spec never anticipated, and that hasn't surfaced as a bug report yet. That residual gap isn't specific to llmlang; no static review process catches a risk nobody thought to check for.

## 6. Implementation status

Built and verified end-to-end (in [`compiler/`](compiler/)):

- `llmlang/parser.py`: the grammar in [the format spec](llmlang-format.md), stack-based (item depth varies by context, so a fixed-depth parser doesn't work).
- `llmlang/extractor.py`: handle-based code lookup (§3.1).
- `llmlang/lockfile_builder.py` / `lockfile_checker.py`: the lockfile, all three cascades in §3, and the guarded `finalize` path (§3.4).
- `llmlang/coverage_checker.py`: opt-in `--coverage` check (§7) that every module- and class-level Python function has a comment handle or an inline `[llm-exempt]` marker; Python-only for now.
- `llmlang/cli.py`: the CLI, self-hosted like everything else in the package (compiles its own `compiler.llm`, same as the rest). Three subcommands: `check [path...]` is the read-only linter surface (§7); `build <file>.llm` and `finalize <file>.llm` are the two write paths, each always scoped to exactly one project's own lockfile (and, for `finalize`, its own change manifest), never something auto-discovery should apply indiscriminately across. `--version`/`--help` are recognized, and an unrecognized command or a flag that doesn't apply to the given command (`--coverage` on `build`, say) is a hard error, not a silent no-op. It wasn't always tracked this way: `build.py` was originally excluded from self-hosting as "just the CLI wrapper," but that exemption turned out to be weaker than the ones used elsewhere (this code encodes real, user-facing contracts: flag-vs-config precedence, the JSON output shape, how multiple paths merge into one report), so it moved into the package as `cli.py` with real entries, and the only things still exempt (`_plural`, `_usage`) are marked with the same `[llm-exempt]` every other trivial helper uses, not an unwritten convention.
- `compiler/build.py`: a thin, untracked shim (not part of the `llmlang` package) that puts the package on `sys.path` and delegates to `llmlang.cli.main()`, for running this tool directly out of a checkout without a full `pip install`. Pre-commit's `language: script` mode needs exactly this, since it executes a repo-relative file directly rather than invoking an installed command.

Compiling (llmlang → code) still isn't automated, but that's not missing software: it's an LLM given the format spec, this doc, and the target `.llm` file, writing code that satisfies every bullet. That's exactly what happened, by hand, for every example in this repo, and it doesn't need a separate portable instructions document restating rules the format spec and this doc already state in full, since that would just be duplication this design's single-sourcing discipline exists to avoid. What `finalize` adds is narrower and more useful: a mechanical guarantee that whoever does the compiling, human or LLM, can't silently skip an entry while doing it.

## 7. Installing llmlang as a linter

The goal: add llmlang's check to a project the same way you'd add any other static-analysis tool, a pre-commit hook, a CI step, a plain `pip install`, without every consumer hand-rolling the invocation.

**Installing.** `pyproject.toml` has real `[build-system]`/`[project]` metadata (setuptools) and a console-script entry point, so `pip install .` (from a checkout) or `pip install git+https://github.com/AlBillington/llmlang.git` (directly, no local checkout needed) both give you a real `llmlang` command anywhere on `PATH`. Not published to PyPI yet, so `pip install llmlang` alone doesn't resolve, but everything else works exactly like an installed tool. The importable package is `llmlang`, living under `compiler/llmlang/` in this repo (`[tool.setuptools.packages.find]` points setuptools at `compiler/` for discovery); the location doesn't affect what you get from installing it.

**Auto-discovery.** `llmlang check` accepts any number of file or directory paths (default: the current directory), auto-discovering every `*.llm` file under a directory argument and checking a `.llm` file argument directly, reporting every failure across every path in one pass rather than stopping at the first. This is what makes a single project-wide hook possible instead of one hook per `.llm` file:

```
llmlang check .
```

**Pre-commit.** [`.pre-commit-hooks.yaml`](.pre-commit-hooks.yaml) at the repo root defines an `llmlang-check` hook using `language: python`: pre-commit pip-installs the hook repo into an isolated venv and invokes the `llmlang` console script, now that real packaging exists to support it. `pass_filenames: false` matters here too: pre-commit's default behavior is to append the list of staged files as trailing arguments, which would collide with `check`'s own path arguments. A consumer wires it up the usual way:

```yaml
repos:
  - repo: https://github.com/AlBillington/llmlang
    rev: <commit-or-tag>
    hooks:
      - id: llmlang-check
```

This repo's own [`.pre-commit-config.yaml`](.pre-commit-config.yaml) dogfoods the hook differently, though: `repo: local` doesn't reliably resolve a local-path `additional_dependencies` entry the way installing an *external* repo does (confirmed by testing, not assumed), so it uses `language: script` pointing at the `compiler/build.py` shim (§6) instead of a real install. A repo checking *itself* has a different constraint than a repo consuming this one as a dependency.

**CI.** With real packaging, a CI job just installs and runs:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- run: pip install git+https://github.com/AlBillington/llmlang.git
- run: llmlang check .
```

This repo's own [workflow](.github/workflows/llmlang-check.yml) uses `pip install .` instead of a git URL, since it's installing and checking itself in the same job; a consumer repo would use the git-URL form above.

**Config.** [`pyproject.toml`](pyproject.toml)'s `[tool.llmlang]` table sets project-level defaults, found by walking up from the current directory until a `pyproject.toml` turns up, or pass `--config PATH` to use a specific file instead of auto-discovery. A CLI flag always overrides the config in either direction:

```toml
[tool.llmlang]
coverage = true       # same as always passing --coverage; --no-coverage still forces it off
exclude = ["vendor"]  # extends, never replaces, the built-in excluded-directory set
```

This repo's own `pyproject.toml` sets `coverage = true`, which is why the CI workflow above can invoke plain `llmlang check .` without spelling out `--coverage`: the config is doing that, not a hardcoded flag. `tomllib` (stdlib since 3.11) is loaded defensively: if it's missing, `--coverage`/`--no-coverage`/`check` still all work, `[tool.llmlang]` is just ignored with a warning naming why. The local pre-commit hook (above) keeps `--coverage` spelled out explicitly rather than relying on this, though, since `language: script` has no way to pin which Python runs it, so it shouldn't assume `tomllib` is there; CI's `setup-python@v5` pins 3.11 explicitly, so the config path is reliable there.

**Coverage exemptions.** A function `--coverage` would otherwise flag can be marked with a bare `[llm-exempt]` comment on the line directly above it (or above its first decorator), same positional rule a handle already follows, and a reason can be written before the tag but isn't required. This lives inline rather than in a side file on purpose: every other traceability concept here (`[llm:name]`, `[llm-test:name]`) is already a comment sitting next to the code it's about, and an exemption moves with the function if it's renamed or relocated, unlike a separate lookup key that can silently go stale.

**Machine-readable output.** `check --output-format json` prints `{"ok": bool, "results": {file: [finding, ...]}}`, each finding a `{category, message, file, line}` object, the same `Finding` records (§3, `llmlang/lockfile.py`) the text report renders, not a separate parse of it, so the two can never drift apart. `message` carries the exact same text the human report shows; `category`/`file`/`line` are there for a caller that wants to act on a finding programmatically instead of reading prose (a GitHub Actions annotation renderer would be the natural next thing built on top of this, though it doesn't exist yet). Progress lines ("checking X") and warnings always go to stderr in either format, so stdout is safe to pipe straight into `jq` or a file.

**Still open**: publishing to PyPI, so `pip install llmlang` alone resolves instead of needing a git URL. Deliberately deferred: this tool's shape has changed multiple times in short order (the exemption mechanism, the CLI structure, the output format), and a published package implies a stability commitment this isn't ready to make yet.

## 8. Summary of open questions

- §3.4: `finalize` guarantees coverage (nothing silently skipped), not correctness (whether a disposition is true); a fabricated disposition is still possible, and still ultimately a human-review problem, same as generated code always has been.
- §5: `@policy:` (§2.3) covers anticipated non-functional concerns, but nothing catches one nobody thought to flag before it surfaces as a bug; not a gap specific to llmlang, but unaddressed here.
- Not yet touched: what compile-time LLM context looks like in practice (how much of the rest of the codebase a given entry's compile step sees), what language(s) beyond Python/HTML/JS the tooling has been proven against, the split-a-method direction of the 1:1 rule (only the merge-bullets direction has come up in practice so far).
- §7 `--coverage` is Python-only: enumerating "every function that exists" needs a real per-language parser, which only exists for Python right now; other languages are silently skipped, not flagged.
- §7 `--coverage` only checks files an `.llm` file already declares (via `walk_files`); it can't catch a whole file nobody ever mentioned in llmlang at all. Same "missing file" gap the 3dprinter-tycoon onboarding stress test surfaced originally, still unaddressed by any mechanical check. Buildable (an `UNMAPPED_FILE` check, same shape as the existing function-level one, just scanning the project tree for files no `.llm` file's `walk_files()` references), just not built yet.

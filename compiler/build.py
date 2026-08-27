#!/usr/bin/env python3
"""
CLI: python build.py check [path...] [--coverage | --no-coverage] [--config PATH] [--output-format text|json]
     python build.py build <llmlang_file>
     python build.py finalize <llmlang_file>
     python build.py --version
     python build.py --help

Any command not in {check, build, finalize} is rejected with an error,
same as an unrecognized flag for whichever command was given (e.g.
--coverage is only valid for check, not build/finalize) - nothing is
silently ignored.

check is the read-only, no-write action - the "linter" surface, matching
ruff/eslint's split between a checking command and a writing one. It
accepts any number of file or directory paths (default: the current
directory), auto-discovering every *.llm file under a directory argument
and checking a .llm file argument directly, reporting every failure
across every path in one pass rather than stopping at the first.
Progress/diagnostic lines ("checking X", path-not-found warnings) always
go to stderr, so stdout stays clean for the actual report in either
--output-format - text (default) or json (a {"ok", "results": {file:
[{category, message, file, line}, ...]}} object, one entry per finding,
built from the exact same Finding records the text report renders).

build and finalize are the write operations - each always requires
exactly one llmlang file, since each is a guarded write for one project's
own lockfile (and, for finalize, its own change manifest), never
something to apply indiscriminately across everything check's discovery
might find.

--coverage is an opt-in modifier on check (ignored otherwise): it also
verifies that every function actually defined in a Python source file has
a comment handle covering it, reporting each uncovered one as
UNMAPPED_CODE. Strict by design - there is no built-in exemption for
dunder methods, private helpers, or anything else; every exemption is a
real, reviewable decision made inline, right above the function it
covers: a bare "[llm-exempt]" comment, optionally with a reason before
the tag (see Compiler/CoverageChecker.py). Python-only for now - files in
other languages are silently skipped, not flagged, since there's no real
parser for them yet to enumerate "every function that exists."

Project-level defaults live in pyproject.toml's [tool.llmlang] table,
found by walking up from the current directory, same discovery pattern
as ruff/black/mypy - or pass --config PATH to use a specific file
instead of auto-discovery. A CLI flag always wins over the config:
--coverage/--no-coverage override [tool.llmlang] coverage = true/false in
either direction, and exclude = ["dir", ...] extends (never replaces) the
built-in excluded-directory set used by check's auto-discovery.

File location needs no discovery step or manifest, ever - the tree
itself already carries it, since a file-typed node's own header
("UrlShortener.py:") is its extension and a folder-typed ancestor's
names are its path.

finalize is the guarded incremental path: it refuses to rebuild unless
<stem>.llmchanges.json - a real, git-tracked sibling file, not a
throwaway CLI argument - covers every entry currently flagged by check.
That file is authored the same way the .llm file itself is (by hand or
by an LLM, reviewed via its own git diff) - a fresh entry is just
{key: "disposition text"}. finalize() upgrades an accepted entry into a
hash-bound record and prunes any entry whose hash no longer matches
current reality, but never invents or edits the disposition text itself.
Plain build stays completely unguarded and has no notion of dispositions
at all, for bootstrapping a brand new lockfile or for a human directly
supervising their own edit.
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

sys.path.insert(0, str(Path(__file__).parent))

from Compiler.CoverageChecker import check_coverage
from Compiler.LockfileBuilder import build, finalize
from Compiler.LockfileChecker import check

_BUILTIN_EXCLUDED_DIR_PARTS = {".git", "__pycache__", "node_modules", "venv", ".venv"}


def _find_pyproject(start: Path):
    start = start.resolve()
    for directory in (start, *start.parents):
        candidate = directory / "pyproject.toml"
        if candidate.exists():
            return candidate
    return None


def _load_config(start: Path, override: Path | None = None) -> dict:
    if override is not None:
        if not override.exists():
            print(f"warning: --config path not found: {override} - ignoring")
            return {}
        pyproject_path = override
    else:
        pyproject_path = _find_pyproject(start)
        if pyproject_path is None:
            return {}

    if tomllib is None:
        print(
            f"warning: found {pyproject_path} but this Python "
            f"({sys.version.split()[0]}) has no tomllib (needs 3.11+) - "
            f"ignoring its [tool.llmlang] config"
        )
        return {}
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("llmlang", {})


def _resolve_coverage(flags: set, config: dict) -> bool:
    if "--no-coverage" in flags:
        return False
    if "--coverage" in flags:
        return True
    return bool(config.get("coverage", False))


def _discover_llm_files(root: Path, extra_exclude: set = frozenset()):
    excluded = _BUILTIN_EXCLUDED_DIR_PARTS | extra_exclude
    return sorted(
        path
        for path in root.rglob("*.llm")
        if not excluded.intersection(path.parts)
    )


def _check_one(llmlang_path: Path, coverage: bool = False) -> tuple[bool, list]:
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")
    try:
        ok, _flagged, findings = check(llmlang_path, lockfile_path)
    except ValueError as e:
        return False, [str(e)]

    if coverage:
        coverage_findings = check_coverage(llmlang_path)
        if coverage_findings:
            ok = False
            findings = findings + coverage_findings

    return ok, findings


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _print_report_text(findings_by_file: dict):
    total = sum(len(findings) for findings in findings_by_file.values())
    if total == 0:
        print("OK — lockfile matches llmlang and code.")
        return

    bar = "=" * 70
    print()
    print(bar)
    print("FAILURES")
    print(bar)
    files_with_findings = 0
    for file_key, findings in findings_by_file.items():
        if not findings:
            continue
        files_with_findings += 1
        print(f"\n{file_key}")
        for finding in findings:
            print(f"  {finding.message}")
    print()
    print(bar)
    print(f"{_plural(total, 'failure')} across {_plural(files_with_findings, 'file')}")
    print(bar)


def _print_report_json(findings_by_file: dict):
    payload = {
        "ok": all(not findings for findings in findings_by_file.values()),
        "results": {
            file_key: [asdict(finding) for finding in findings]
            for file_key, findings in findings_by_file.items()
        },
    }
    print(json.dumps(payload, indent=2))


def _run_check(paths: list, flags: set, config_override: Path | None, output_format: str):
    config = _load_config(Path("."), config_override)
    coverage = _resolve_coverage(flags, config)
    extra_exclude = set(config.get("exclude", []))

    llm_files = []
    for path in paths:
        if path.is_dir():
            llm_files.extend(_discover_llm_files(path, extra_exclude=extra_exclude))
        elif path.is_file():
            llm_files.append(path)
        else:
            print(f"warning: path not found: {path}", file=sys.stderr)

    llm_files = sorted(set(llm_files))
    if not llm_files:
        print(f"No .llm files found under {', '.join(str(p) for p in paths)}", file=sys.stderr)
        sys.exit(1)

    findings_by_file = {}
    for llmlang_path in llm_files:
        print(f"checking {llmlang_path}", file=sys.stderr)
        ok, findings = _check_one(llmlang_path, coverage=coverage)
        findings_by_file[str(llmlang_path)] = findings

    if output_format == "json":
        _print_report_json(findings_by_file)
    else:
        _print_report_text(findings_by_file)
    sys.exit(0 if all(not f for f in findings_by_file.values()) else 1)


def _run_build(positional: list):
    if len(positional) != 1:
        print("usage: build.py build <llmlang_file>")
        sys.exit(1)
    llmlang_path = Path(positional[0])
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")
    try:
        build(llmlang_path, lockfile_path)
    except ValueError as e:
        print(e)
        sys.exit(1)
    print(f"Wrote {lockfile_path}")


def _run_finalize(positional: list):
    if len(positional) != 1:
        print("usage: build.py finalize <llmlang_file>")
        sys.exit(1)
    llmlang_path = Path(positional[0])
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")
    changes_path = llmlang_path.parent / (llmlang_path.stem + ".llmchanges.json")
    try:
        finalize(llmlang_path, lockfile_path, changes_path)
    except ValueError as e:
        print(e)
        sys.exit(1)
    print(f"Wrote {lockfile_path}")


_VERSION = "0.1.0"

_ALLOWED_FLAGS = {
    "check": {"--coverage", "--no-coverage"},
    "build": set(),
    "finalize": set(),
}


_OUTPUT_FORMATS = {"text", "json"}


def _usage():
    print("usage: build.py check [path...] [--coverage | --no-coverage] [--config PATH] [--output-format text|json]")
    print("       build.py build <llmlang_file>")
    print("       build.py finalize <llmlang_file>")
    print("       build.py --version")
    print("       build.py --help")


def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        _usage()
        return

    if not args:
        _usage()
        sys.exit(1)

    if args[0] == "--version":
        print(f"llmlang {_VERSION}")
        return

    action, rest = args[0], args[1:]
    if action not in _ALLOWED_FLAGS:
        print(f"unknown command: {action!r}")
        _usage()
        sys.exit(1)

    flags = set()
    positional = []
    config_override = None
    output_format = "text"
    value_flags_seen = set()
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--config":
            i += 1
            if i >= len(rest):
                print("--config requires a path argument")
                sys.exit(1)
            config_override = Path(rest[i])
            value_flags_seen.add("--config")
        elif a == "--output-format":
            i += 1
            if i >= len(rest):
                print("--output-format requires a value argument")
                sys.exit(1)
            output_format = rest[i]
            if output_format not in _OUTPUT_FORMATS:
                print(f"unknown --output-format {output_format!r} (expected one of: {', '.join(sorted(_OUTPUT_FORMATS))})")
                sys.exit(1)
            value_flags_seen.add("--output-format")
        elif a.startswith("--"):
            flags.add(a)
        else:
            positional.append(a)
        i += 1

    unknown_flags = flags - _ALLOWED_FLAGS[action]
    if action != "check":
        unknown_flags = unknown_flags | value_flags_seen
    if unknown_flags:
        print(f"unknown flag(s) for '{action}': {', '.join(sorted(unknown_flags))}")
        _usage()
        sys.exit(1)

    if action == "check":
        paths = [Path(p) for p in positional] or [Path(".")]
        _run_check(paths, flags, config_override, output_format)
    elif action == "build":
        _run_build(positional)
    elif action == "finalize":
        _run_finalize(positional)


if __name__ == "__main__":
    main()

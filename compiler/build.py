#!/usr/bin/env python3
"""
CLI: python build.py <llmlang_file> [--check | --finalize] [--coverage]
     python build.py --check [root_dir] [--coverage]

--coverage is an opt-in modifier on --check (ignored otherwise): it also
verifies that every function actually defined in a Python source file has
a comment handle covering it, reporting each uncovered one as
UNMAPPED_CODE. Strict by design - there is no built-in exemption for
dunder methods, private helpers, or anything else; every exemption is a
real, reviewable decision recorded in <stem>.llmchanges.json's "exempt"
section (see Compiler/CoverageChecker.py). Python-only for now - files in
other languages are silently skipped, not flagged, since there's no real
parser for them yet to enumerate "every function that exists."

File location needs no discovery step or manifest, ever - the tree
itself already carries it, since a file-typed node's own header
("UrlShortener.py:") is its extension and a folder-typed ancestor's
names are its path.

--check with no file argument discovers every *.llm file under
root_dir (default: the current directory) and checks each one,
reporting all of them rather than stopping at the first failure -
same "report every deficiency in one pass" behavior a single-file
--check already has, just widened to a whole project. --finalize and
plain (no-flag) rebuild always require an explicit file - each is a
guarded write for one project, not something to apply indiscriminately
across everything discovery happens to find.

--finalize is the guarded incremental path: it refuses to rebuild
unless <stem>.llmchanges.json - a real, git-tracked sibling file, not
a throwaway CLI argument - covers every entry currently flagged by
--check. That file is authored the same way the .llm file itself is
(by hand or by an LLM, reviewed via its own git diff) - a fresh entry
is just {key: "disposition text"}. finalize() upgrades an accepted
entry into a hash-bound record and prunes any entry whose hash no
longer matches current reality, but never invents or edits the
disposition text itself. Plain (no-flag) rebuild stays completely
unguarded and has no notion of dispositions at all, for bootstrapping
a brand new lockfile or for a human directly supervising their own
edit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from Compiler.CoverageChecker import check_coverage
from Compiler.LockfileBuilder import build, finalize
from Compiler.LockfileChecker import check

_EXCLUDED_DIR_PARTS = {".git", "__pycache__", "node_modules", "venv", ".venv"}


def _discover_llm_files(root: Path):
    return sorted(
        path
        for path in root.rglob("*.llm")
        if not _EXCLUDED_DIR_PARTS.intersection(path.parts)
    )


def _check_one(llmlang_path: Path, coverage: bool = False) -> tuple[bool, list]:
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")
    try:
        ok, _flagged, findings = check(llmlang_path, lockfile_path)
    except ValueError as e:
        return False, [str(e)]

    if coverage:
        changes_path = llmlang_path.parent / (llmlang_path.stem + ".llmchanges.json")
        coverage_findings = check_coverage(llmlang_path, changes_path)
        if coverage_findings:
            ok = False
            findings = findings + coverage_findings

    return ok, findings


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _print_report(findings_by_file: dict):
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
            print(f"  {finding}")
    print()
    print(bar)
    print(f"{_plural(total, 'failure')} across {_plural(files_with_findings, 'file')}")
    print(bar)


def _check_project(root: Path, coverage: bool = False):
    llm_files = _discover_llm_files(root)
    if not llm_files:
        print(f"No .llm files found under {root}")
        sys.exit(1)

    findings_by_file = {}
    for llmlang_path in llm_files:
        print(f"checking {llmlang_path}")
        _ok, findings = _check_one(llmlang_path, coverage=coverage)
        findings_by_file[str(llmlang_path)] = findings

    _print_report(findings_by_file)
    sys.exit(0 if all(not f for f in findings_by_file.values()) else 1)


def main():
    args = sys.argv[1:]
    flags = {a for a in args if a.startswith("--")}
    positional = [a for a in args if not a.startswith("--")]

    coverage = "--coverage" in flags

    if "--check" in flags and (not positional or Path(positional[0]).is_dir()):
        root = Path(positional[0]) if positional else Path(".")
        _check_project(root, coverage=coverage)
        return

    if not positional:
        print("usage: build.py <llmlang_file> [--check | --finalize] [--coverage]")
        print("       build.py --check [root_dir] [--coverage]")
        sys.exit(1)

    llmlang_path = Path(positional[0])
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")

    if "--check" in flags:
        ok, findings = _check_one(llmlang_path, coverage=coverage)
        _print_report({str(llmlang_path): findings})
        sys.exit(0 if ok else 1)

    if "--finalize" in flags:
        changes_path = llmlang_path.parent / (llmlang_path.stem + ".llmchanges.json")
        try:
            finalize(llmlang_path, lockfile_path, changes_path)
        except ValueError as e:
            print(e)
            sys.exit(1)
        print(f"Wrote {lockfile_path}")
        return

    try:
        build(llmlang_path, lockfile_path)
    except ValueError as e:
        print(e)
        sys.exit(1)
    print(f"Wrote {lockfile_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
CLI: python build.py <llmlang_file> [--check | --finalize]
     python build.py --check [root_dir]

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

from Compiler.LockfileBuilder import build, finalize
from Compiler.LockfileChecker import check

_EXCLUDED_DIR_PARTS = {".git", "__pycache__", "node_modules", "venv", ".venv"}


def _discover_llm_files(root: Path):
    return sorted(
        path
        for path in root.rglob("*.llm")
        if not _EXCLUDED_DIR_PARTS.intersection(path.parts)
    )


def _check_one(llmlang_path: Path) -> bool:
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")
    try:
        ok, _ = check(llmlang_path, lockfile_path)
    except ValueError as e:
        print(e)
        return False
    return ok


def _check_project(root: Path):
    llm_files = _discover_llm_files(root)
    if not llm_files:
        print(f"No .llm files found under {root}")
        sys.exit(1)

    overall_ok = True
    for llmlang_path in llm_files:
        print(f"checking {llmlang_path}")
        if not _check_one(llmlang_path):
            overall_ok = False
    sys.exit(0 if overall_ok else 1)


def main():
    args = sys.argv[1:]
    flags = {a for a in args if a.startswith("--")}
    positional = [a for a in args if not a.startswith("--")]

    if "--check" in flags and (not positional or Path(positional[0]).is_dir()):
        root = Path(positional[0]) if positional else Path(".")
        _check_project(root)
        return

    if not positional:
        print("usage: build.py <llmlang_file> [--check | --finalize]")
        print("       build.py --check [root_dir]")
        sys.exit(1)

    llmlang_path = Path(positional[0])
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")

    if "--check" in flags:
        sys.exit(0 if _check_one(llmlang_path) else 1)

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

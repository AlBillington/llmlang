"""
CLI: python build.py <llmlang_file> [--check | --finalize]

File location needs no discovery step or manifest, ever - the tree
itself already carries it, since a file-typed node's own header
("UrlShortener.py:") is its extension and a folder-typed ancestor's
names are its path.

--finalize is the guarded incremental path: it refuses to rebuild
unless <stem>.llmchanges.json - a real, git-tracked sibling file, not
a throwaway CLI argument - covers every entry currently flagged by
--check. That file is authored the same way the .llm file itself is
(by hand or by an LLM, reviewed via its own git diff), never written
by this tool; --finalize only reads it. Plain (no-flag) rebuild stays
unguarded, for bootstrapping a brand new lockfile or for a human
directly supervising their own edit.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from Compiler.LockfileBuilder import build
from Compiler.LockfileChecker import check


def main():
    llmlang_path = Path(sys.argv[1])
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")

    if "--check" in sys.argv:
        ok, _ = check(llmlang_path, lockfile_path)
        sys.exit(0 if ok else 1)

    if "--finalize" in sys.argv:
        changes_path = llmlang_path.parent / (llmlang_path.stem + ".llmchanges.json")
        manifest = json.loads(changes_path.read_text()) if changes_path.exists() else {}
        try:
            build(llmlang_path, lockfile_path, manifest=manifest)
        except ValueError as e:
            print(e)
            sys.exit(1)
        print(f"Wrote {lockfile_path}")
        return

    build(llmlang_path, lockfile_path)
    print(f"Wrote {lockfile_path}")


if __name__ == "__main__":
    main()

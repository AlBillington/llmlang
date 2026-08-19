"""
CLI: python build.py <llmlang_file> [--check]

File location needs no discovery step or manifest, ever - the tree
itself already carries it, since a file-typed node's own header
("UrlShortener.py:") is its extension and a folder-typed ancestor's
names are its path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from Compiler.LockfileBuilder import build
from Compiler.LockfileChecker import check


def main():
    llmlang_path = Path(sys.argv[1])
    lockfile_path = llmlang_path.parent / (llmlang_path.stem + ".llmlock")

    if "--check" in sys.argv:
        ok = check(llmlang_path, lockfile_path)
        sys.exit(0 if ok else 1)

    build(llmlang_path, lockfile_path)
    print(f"Wrote {lockfile_path}")


if __name__ == "__main__":
    main()

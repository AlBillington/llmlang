#!/usr/bin/env python3
"""
Thin script entry point for running this tool without a full pip install
(e.g. pre-commit's language: script mode, which executes a repo-relative
file directly rather than invoking an installed command). All real CLI
logic lives in llmlang/cli.py, tracked like everything else in
compiler.llm - this file is deliberately just enough glue to put the
package on sys.path and delegate, since it can't use a relative import
the way cli.py does when run this way (no parent package context).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from llmlang.cli import main

if __name__ == "__main__":
    main()

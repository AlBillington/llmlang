"""
Checks that every function actually defined in a Python source file has a
comment handle covering it, or is explicitly exempted in the changes file.

Python-only for now: enumerating "every function that exists" requires a
real parser for the language, unlike hash checking (which only ever
searches for a comment it already expects to find, so it never needed
one). Files in unsupported languages are silently skipped, not flagged -
this only ever reports what it can actually verify.

Deliberately scoped to functions/methods defined at module or class level.
A closure nested inside another function is skipped: it has no stable
qualified name of its own to report or exempt, and it's already swept
into its enclosing function's own tracked code region by the "next handle
or EOF" rule, so it isn't actually unverified.

Opt-in and strict: there is no built-in notion of a trivial function that
doesn't need a handle (no automatic exemption for dunder methods, private
helpers, or anything else). Every exemption is a real, reviewable decision
recorded in <stem>.llmchanges.json's "exempt" section, keyed by
"{file_rel}::{qualified_name}" with a plain-string reason - permanent, not
hash-bound, since it's a standing claim ("this will never need a handle"),
not a disposition explaining away a particular drift.
"""
import ast
import json
from pathlib import Path

from Compiler.Extractor import handle_line_numbers
from Compiler.Parser import parse, walk_files

EXEMPT_KEY = "exempt"


def _qualified_functions(text: str):
    """Yields (qualified_name, def_line) for every module- or class-level
    function/method - def_line is the line a handle comment (or the first
    decorator, if any) needs to sit directly above."""
    tree = ast.parse(text)

    def walk(node, class_stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from walk(child, class_stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                first_line = child.decorator_list[0].lineno if child.decorator_list else child.lineno
                yield ".".join(class_stack + [child.name]), first_line

    yield from walk(tree, [])


def _load_exemptions(changes_path: Path) -> dict:
    if not changes_path.exists():
        return {}
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    return changes.get(EXEMPT_KEY, {})


# checks every module- and class-level Python function against comment handles and changes-file exemptions, reporting each uncovered one as UNMAPPED_CODE [llm:Compiler.CoverageChecker.check_coverage]
def check_coverage(llmlang_path: Path, changes_path: Path) -> list:
    root = parse(llmlang_path)
    exemptions = _load_exemptions(changes_path)
    findings = []

    for file_rel, ext in walk_files(root):
        if ext != "py":
            continue
        file_path = llmlang_path.parent / file_rel
        text = file_path.read_text(encoding="utf-8")
        handle_lines = handle_line_numbers(file_path)

        for qualified_name, def_line in _qualified_functions(text):
            if (def_line - 1) in handle_lines:
                continue
            exemption_key = f"{file_rel}::{qualified_name}"
            if exemption_key in exemptions:
                continue
            findings.append(
                "UNMAPPED_CODE (no comment handle covers this function, and it isn't exempted in "
                f'{changes_path.name} - add a handle, or add "{exemption_key}" to its "exempt" '
                f"section with a reason): {qualified_name} — {file_rel}:{def_line}"
            )

    return findings

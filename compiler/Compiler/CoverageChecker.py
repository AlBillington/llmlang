"""
Checks that every function actually defined in a Python source file has a
comment handle covering it, or is marked exempt with a bare [llm-exempt]
comment.

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
helpers, or anything else). Every exemption is a real, reviewable
decision made inline, right next to the function it covers: a bare
"[llm-exempt]" comment on the line directly above the function (or above
its first decorator) - same positional rule a handle already follows. A
reason can be written before the tag on the same line, matching the
human-text-first-tag-last convention used everywhere else, but isn't
required.
"""
import ast
import re
from pathlib import Path

from Compiler.Extractor import handle_line_numbers
from Compiler.Parser import parse, walk_files

_EXEMPT_RE = re.compile(r"\[llm-exempt\]")


# private helper of check_coverage(), not independent architecture [llm-exempt]
def _qualified_functions(text: str):
    """Yields (qualified_name, def_line) for every module- or class-level
    function/method - def_line is the line a handle or exemption comment
    needs to sit directly above (the first decorator's line, if any)."""
    tree = ast.parse(text)

    def walk(node, class_stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from walk(child, class_stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                first_line = child.decorator_list[0].lineno if child.decorator_list else child.lineno
                yield ".".join(class_stack + [child.name]), first_line

    yield from walk(tree, [])


# private helper of check_coverage(), not independent architecture [llm-exempt]
def _exempt_line_numbers(text: str) -> set:
    return {i + 1 for i, line in enumerate(text.splitlines()) if _EXEMPT_RE.search(line)}


# checks every module- and class-level Python function against comment handles and inline [llm-exempt] markers, reporting each uncovered one as UNMAPPED_CODE [llm:Compiler.CoverageChecker.check_coverage]
def check_coverage(llmlang_path: Path) -> list:
    root = parse(llmlang_path)
    findings = []

    for file_rel, ext in walk_files(root):
        if ext != "py":
            continue
        file_path = llmlang_path.parent / file_rel
        text = file_path.read_text(encoding="utf-8")
        handle_lines = handle_line_numbers(file_path)
        exempt_lines = _exempt_line_numbers(text)

        for qualified_name, def_line in _qualified_functions(text):
            if (def_line - 1) in handle_lines or (def_line - 1) in exempt_lines:
                continue
            findings.append(
                "UNMAPPED_CODE (no comment handle covers this function, and it isn't marked "
                '"[llm-exempt]" either - add a handle, or add "# [llm-exempt]" directly above it, '
                f"optionally with a reason before the tag): {qualified_name} — {file_rel}:{def_line}"
            )

    return findings

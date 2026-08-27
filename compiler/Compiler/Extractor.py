"""
Locates the code implementing an llmlang item by searching for its
canonical-name comment handle placed immediately before it - for example
`[llm:Backend.UrlShortener.create_short_code]` - and taking everything
up to the next handle in the file (or end of file, for the last one).

This works identically regardless of the file's language, because it
never parses anything beyond that literal substring. The only place a
language's comment syntax matters at all is writing a new handle (it
needs a valid comment prefix so it doesn't break compilation) - never
finding one.

Deliberately not heuristic: this rule is exactly "next handle, or EOF" -
nothing inferred from indentation or blank lines. A region can include
unrelated code sitting between two handles (known, accepted coarseness),
but what it includes never depends on how that code happens to be
formatted.
"""
import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


_SOURCE_COMMENT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}


# stores a linked llm-test comment and the backing code it anchors [llm:Compiler.Extractor.TestComment]
@dataclass(frozen=True)
class TestComment:
    node: str
    text: str
    path: str
    code: str

    @property
    def code_hash(self) -> str:
        return hashlib.sha256(self.code.encode()).hexdigest()


def _all_handles(text: str):
    handles = []
    for match in re.finditer(r"\[llm:([a-zA-Z0-9_.]+)\]", text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        handles.append((match.group(1), line_start))
    return handles


# extracts the code implementing an entry by locating its comment handle and taking everything from the handle's own comment line up to the next handle [llm:Compiler.Extractor.extract_by_handle]
def extract_by_handle(file_path: Path, key: str):
    # code_start begins at the handle's own comment line (not after it),
    # so the summary comment is part of code_hash - otherwise a comment
    # can drift arbitrarily far from the llmlang summary it's supposed to
    # match with nothing ever detecting it, since nothing else compares
    # the two directly
    text = file_path.read_text(encoding="utf-8")
    handles = _all_handles(text)

    for i, (handle_key, line_start) in enumerate(handles):
        if handle_key != key:
            continue
        code_end = handles[i + 1][1] if i + 1 < len(handles) else len(text)
        return text[line_start:code_end].strip("\n")

    return None


def _clean_comment_text(text: str) -> str:
    cleaned = text.strip()
    for prefix in ("#", "//", "<!--", "*"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned.rstrip("-").strip()


def _repo_root(path: Path):
    # relative paths (e.g. Path(".")) have no .parents to walk until
    # resolved - without this, running from anywhere but the repo root
    # silently fails to find it and falls back to the wrong base
    path = path.resolve()
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _relative_path(path: Path, base_path: Path) -> str:
    try:
        return path.relative_to(base_path).as_posix()
    except ValueError:
        return path.as_posix()


# chooses where llm-test comments are scanned [llm:Compiler.Extractor.test_comment_roots]
def test_comment_roots(llmlang_path: Path):
    # resolved up front so this gives the same answer regardless of
    # whether llmlang_path was relative or absolute, or what the
    # caller's cwd happened to be
    llm_dir = llmlang_path.resolve().parent
    roots = [llm_dir]
    repo_root = _repo_root(llm_dir)
    if repo_root:
        tests_root = repo_root / "tests"
        if tests_root.exists() and tests_root not in roots:
            roots.append(tests_root)
    return roots


# chooses the stable base path for test trace paths [llm:Compiler.Extractor.test_comment_base]
def test_comment_base(llmlang_path: Path):
    llm_dir = llmlang_path.resolve().parent
    return _repo_root(llm_dir) or llm_dir


def _python_block_for_line(text: str, line_number: int):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for node in nodes:
        if node.lineno == line_number + 1:
            return node
    candidates = []
    for node in nodes:
        end_lineno = getattr(node, "end_lineno", None)
        if end_lineno is None:
            continue
        if node.lineno <= line_number <= end_lineno:
            candidates.append(node)
    if not candidates:
        return None
    return max(candidates, key=lambda node: node.lineno)


def _fallback_block_end(lines: list, start_index: int) -> int:
    for i in range(start_index + 1, len(lines)):
        if "[llm-test:" in lines[i]:
            return i
    return len(lines)


def _test_code_for_comment(path: Path, text: str, line_index: int) -> str:
    lines = text.splitlines()
    if path.suffix == ".py":
        node = _python_block_for_line(text, line_index + 1)
        if node is not None:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno]).strip("\n")
    end_index = _fallback_block_end(lines, line_index)
    return "\n".join(lines[line_index:end_index]).strip("\n")


# collects llm-test comments by canonical node name [llm:Compiler.Extractor.test_comments_by_node]
def test_comments_by_node(root_paths, base_path: Path | None = None):
    comments = {}
    if isinstance(root_paths, Path):
        root_paths = [root_paths]
    base_path = base_path or root_paths[0]
    for root_path in root_paths:
        for path in root_path.rglob("*"):
            if (
                not path.is_file()
                or path.suffix not in _SOURCE_COMMENT_SUFFIXES
                or any(part in {".git", "__pycache__"} for part in path.parts)
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_index, line in enumerate(text.splitlines()):
                for match in re.finditer(r"\[llm-test:([a-zA-Z0-9_.]+)\]", line):
                    comment_text = _clean_comment_text(line[: match.start()])
                    node = match.group(1)
                    comments.setdefault(node, []).append(
                        TestComment(
                            node=node,
                            text=comment_text,
                            path=_relative_path(path, base_path),
                            code=_test_code_for_comment(path, text, line_index),
                        )
                    )
    return comments

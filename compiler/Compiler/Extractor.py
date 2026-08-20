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
import re
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


def _all_handles(text: str):
    handles = []
    for match in re.finditer(r"\[llm:([a-zA-Z0-9_.]+)\]", text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        handles.append((match.group(1), line_start))
    return handles


# extracts the code implementing an entry by locating its comment handle and taking everything up to the next handle [llm:Compiler.Extractor.extract_by_handle]
def extract_by_handle(file_path: Path, key: str):
    text = file_path.read_text()
    handles = _all_handles(text)

    for i, (handle_key, line_start) in enumerate(handles):
        if handle_key != key:
            continue
        code_start = text.find("\n", line_start) + 1
        code_end = handles[i + 1][1] if i + 1 < len(handles) else len(text)
        return text[code_start:code_end].strip("\n")

    return None


def _clean_comment_text(text: str) -> str:
    cleaned = text.strip()
    for prefix in ("#", "//", "<!--", "*"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    return cleaned.rstrip("-").strip()


# chooses where llm-test comments are scanned [llm:Compiler.Extractor.test_comment_roots]
def test_comment_roots(llmlang_path: Path):
    roots = [llmlang_path.parent]
    for parent in (llmlang_path.parent, *llmlang_path.parents):
        if not (parent / ".git").exists():
            continue
        tests_root = parent / "tests"
        if tests_root.exists() and tests_root not in roots:
            roots.append(tests_root)
        break
    return roots


# collects llm-test comments by canonical node name [llm:Compiler.Extractor.test_comments_by_node]
def test_comments_by_node(root_paths):
    comments = {}
    if isinstance(root_paths, Path):
        root_paths = [root_paths]
    for root_path in root_paths:
        for path in root_path.rglob("*"):
            if (
                not path.is_file()
                or path.suffix not in _SOURCE_COMMENT_SUFFIXES
                or any(part in {".git", "__pycache__"} for part in path.parts)
            ):
                continue
            try:
                text = path.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for line in text.splitlines():
                for match in re.finditer(r"\[llm-test:([a-zA-Z0-9_.]+)\]", line):
                    comment_text = _clean_comment_text(line[: match.start()])
                    comments.setdefault(match.group(1), set()).add(comment_text)
    return comments

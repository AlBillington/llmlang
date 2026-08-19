"""
Locates the code implementing an llmlang item by searching for a short
comment handle placed immediately before it - `[llm:function0]`,
`[llm:data0]`, etc. - and taking everything up to the next handle in the
file (or end of file, for the last one).

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


def _all_handles(text: str):
    handles = []
    for match in re.finditer(r"\[llm:([a-zA-Z0-9_.]+)\]", text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        handles.append((match.group(1), line_start))
    return handles


# extracts the code implementing an entry by locating its comment handle and taking everything up to the next handle [llm:extract_by_handle]
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

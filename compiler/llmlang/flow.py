"""Generates a sibling .llmflow view from @entry-point entries in an llmlang
tree. The flow file is a build output, never hand-edited: every → call /
← return line already lives in the referenced entry's own llmlang bullets
(llmlang-format.md §4f), so there is nothing left to author here - only to
compose and render.
"""
from pathlib import Path

from llmlang.parser import walk_entries, walk_entry_points

_ARROW_PREFIXES = ("→ call ", "← return ")


# private helper of generate_flow(), not independent architecture [llm-exempt]
def flow_path_for_llmlang(llmlang_path: Path) -> Path:
    return llmlang_path.parent / (llmlang_path.stem + ".llmflow")


# private helper of generate_flow(), not independent architecture [llm-exempt]
def _line_depth_and_text(bullet: str) -> tuple[int, str]:
    depth = len(bullet) - len(bullet.lstrip("\t"))
    return depth, bullet.lstrip("\t")


# private helper of generate_flow(), not independent architecture [llm-exempt]
def _return_text(text: str):
    body = text[2:] if text.startswith("- ") else text
    return body if body.startswith("returns ") else None


# private helper of generate_flow(), not independent architecture [llm-exempt]
def _render_line(text: str, abs_depth: int) -> str:
    if text.startswith(_ARROW_PREFIXES):
        return "\t" * abs_depth + text
    return_text = _return_text(text)
    if return_text is not None:
        return "\t" * abs_depth + "←---- " + return_text
    if text.startswith("- "):
        return "\t" * abs_depth + text
    return "\t" * abs_depth + "- " + text


# private helper of generate_flow(), not independent architecture [llm-exempt]
def _match_targets(target: str, entry_keys: set) -> list:
    if target in entry_keys:
        return [target]
    return [key for key in entry_keys if key.endswith("." + target)]


# private helper of generate_flow(), not independent architecture [llm-exempt]
def _render_bullets(bullets, base_indent, entry_keys, bullets_by_key, visited, errors, source_key, call_depth=None):
    out = []
    for bullet in bullets:
        depth, text = _line_depth_and_text(bullet)
        abs_depth = base_indent + depth
        return_text = _return_text(text)
        if depth == 0 and call_depth is not None and return_text is not None:
            # the callee's own trailing return sits at the calling → call
            # line's own depth, not nested inside the callee's body - it
            # marks control coming back out to the caller's level. The
            # dash leader keeps it visually distinct from a sibling bullet
            # at that same depth despite the jump.
            out.append("\t" * call_depth + "←---- " + return_text)
        else:
            out.append(_render_line(text, abs_depth))
        if not text.startswith("→ call "):
            continue
        target = text[len("→ call "):].strip()
        if " via " in target:
            continue
        matches = _match_targets(target, entry_keys)
        if len(matches) == 0:
            errors.append({
                "source": source_key,
                "message": f"unresolved flow call target {target!r}: no matching llmlang entry",
            })
            continue
        if len(matches) > 1:
            errors.append({
                "source": source_key,
                "message": f"ambiguous flow call target {target!r}: matches {sorted(matches)}",
            })
            continue
        resolved = matches[0]
        if resolved in visited:
            continue
        visited.add(resolved)
        out.extend(_render_bullets(
            bullets_by_key.get(resolved, []), abs_depth + 1, entry_keys,
            bullets_by_key, visited, errors, resolved, call_depth=abs_depth,
        ))
    return out


# private helper of generate_flow(), not independent architecture [llm-exempt]
def _entry_point_header(tracking_key: str, label, summary: str) -> str:
    if isinstance(label, str) and label:
        return label
    return f"{tracking_key} ({summary}):"


# composes a .llmflow view by walking every @entry-point entry and inlining each → call target's own bullets, recursively, expanding each referenced entry only the first time it's reached in a given trace [llm:llmlang.flow.generate_flow]
def generate_flow(entry_points: list, all_entries: dict) -> tuple[str, list]:
    """entry_points: [(tracking_key, label), ...] from walk_entry_points().
    all_entries: tracking_key -> {"summary": str, "bullets": [str, ...]} for
    every named entry, bullets already filtered to real content (no "+
    summary" or "~ test" lines - those aren't part of the call/behavior
    trace). Returns (rendered_text, errors); errors is a list of
    {"source": tracking_key, "message": str} for every call target that
    didn't resolve to exactly one known entry."""
    if not entry_points:
        return "", []

    entry_keys = set(all_entries)
    errors = []
    sections = []
    for tracking_key, label in entry_points:
        entry = all_entries.get(tracking_key)
        if entry is None:
            continue
        header = _entry_point_header(tracking_key, label, entry["summary"])
        visited = {tracking_key}
        rendered = _render_bullets(
            entry["bullets"], 1, entry_keys, {k: v["bullets"] for k, v in all_entries.items()},
            visited, errors, tracking_key,
        )
        sections.append(header + "\n" + "\n".join(rendered))

    return "\n\n".join(sections) + "\n", errors


# private helper of generate_flow_for_tree(), not independent architecture [llm-exempt]
def _entries_for_flow(root) -> dict:
    result = {}
    for _file_rel, _handle_key, tracking_key, bullets, _line in walk_entries(root):
        summary = ""
        content = []
        for bullet in bullets:
            if bullet.startswith("+ "):
                summary = bullet[2:]
            elif bullet.startswith("~ "):
                continue
            else:
                content.append(bullet)
        result[tracking_key] = {"summary": summary, "bullets": content}
    return result


# builds the entry-point list and entry content from a parsed llmlang tree, then composes the flow view [llm:llmlang.flow.generate_flow_for_tree]
def generate_flow_for_tree(root) -> tuple[str, list]:
    entry_points = list(walk_entry_points(root))
    all_entries = _entries_for_flow(root)
    return generate_flow(entry_points, all_entries)

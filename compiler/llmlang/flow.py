"""Flow-file parsing and hash records for lockfile verification."""
import hashlib
from pathlib import Path


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# private helper of flow_refs(), not independent architecture [llm-exempt]
def flow_path_for_llmlang(llmlang_path: Path) -> Path:
    return llmlang_path.parent / (llmlang_path.stem + ".llmflow")


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _line_depth(line: str) -> int:
    return len(line) - len(line.lstrip("\t"))


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _call_target(line: str) -> str | None:
    stripped = line.strip()
    marker = "→ call "
    if stripped.startswith(marker):
        return stripped[len(marker) :].strip()
    return None


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _is_external_target(target: str) -> bool:
    return " via " in target


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _match_targets(target: str, entry_keys: set[str]) -> list[str]:
    if target in entry_keys:
        return [target]
    return [key for key in entry_keys if key.endswith("." + target)]


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _call_block(lines: list[str], start_index: int) -> str:
    start_depth = _line_depth(lines[start_index])
    end_index = start_index + 1
    while end_index < len(lines):
        if lines[end_index].strip() and _line_depth(lines[end_index]) <= start_depth:
            break
        end_index += 1
    return "\n".join(lines[start_index:end_index])


# returns hash records for internal function references in the sibling flow file, plus any unresolved/ambiguous call targets [llm:llmlang.flow.flow_refs]
def flow_refs(llmlang_path: Path, entries: dict) -> tuple[dict, list[dict]]:
    """Return (refs, errors) for the sibling .llmflow file, if present.

    A flow reference is keyed by flow file and canonical llmlang entry.
    When an entry appears multiple times in one flow file, its flow hash
    combines every call block in source order so the disposition reviews
    the function-flow relationship once.

    A call target that can't be resolved to exactly one entry (missing or
    ambiguous) does not raise: it's reported as an error record with the
    1-based source line, so a caller can surface it as a normal finding
    without losing every other finding for the file. Resolvable refs are
    still returned alongside any errors.
    """
    flow_path = flow_path_for_llmlang(llmlang_path)
    if not flow_path.exists():
        return {}, []

    lines = flow_path.read_text(encoding="utf-8").splitlines()
    entry_keys = set(entries)
    blocks_by_entry = {}
    call_names_by_entry = {}
    errors = []

    for i, line in enumerate(lines):
        target = _call_target(line)
        if target is None:
            continue
        matches = _match_targets(target, entry_keys)
        if len(matches) == 1:
            resolved = matches[0]
        elif len(matches) == 0:
            if not _is_external_target(target):
                errors.append({
                    "line": i + 1,
                    "message": f"unresolved flow call target {target!r}: no matching llmlang entry",
                })
            continue
        else:
            errors.append({
                "line": i + 1,
                "message": f"ambiguous flow call target {target!r}: matches {sorted(matches)}",
            })
            continue
        blocks_by_entry.setdefault(resolved, []).append(_call_block(lines, i))
        call_names_by_entry.setdefault(resolved, set()).add(target)

    rel_flow = flow_path.relative_to(llmlang_path.parent).as_posix()
    refs = {}
    for entry_key, blocks in blocks_by_entry.items():
        entry = entries[entry_key]
        key = f"flow:{rel_flow}::{entry_key}"
        refs[key] = {
            "flow": rel_flow,
            "entry": entry_key,
            "call_names": sorted(call_names_by_entry[entry_key]),
            "entry_spec_hash": entry["spec_hash"],
            "code_hash": entry["code_hash"],
            "flow_ref_hash": _sha256("\n\n---\n\n".join(blocks)),
        }
    return refs, errors

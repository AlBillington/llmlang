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
def _resolve_target(target: str, entry_keys: set[str]) -> str | None:
    if target in entry_keys:
        return target
    matches = [key for key in entry_keys if key.endswith("." + target)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"ambiguous flow call target {target!r}: {matches}")
    return None


# private helper of flow_refs(), not independent architecture [llm-exempt]
def _call_block(lines: list[str], start_index: int) -> str:
    start_depth = _line_depth(lines[start_index])
    end_index = start_index + 1
    while end_index < len(lines):
        if lines[end_index].strip() and _line_depth(lines[end_index]) <= start_depth:
            break
        end_index += 1
    return "\n".join(lines[start_index:end_index])


# returns hash records for internal function references in the sibling flow file [llm:llmlang.flow.flow_refs]
def flow_refs(llmlang_path: Path, entries: dict) -> dict:
    """Return flow lock records for the sibling .llmflow file, if present.

    A flow reference is keyed by flow file and canonical llmlang entry.
    When an entry appears multiple times in one flow file, its flow hash
    combines every call block in source order so the disposition reviews
    the function-flow relationship once.
    """
    flow_path = flow_path_for_llmlang(llmlang_path)
    if not flow_path.exists():
        return {}

    lines = flow_path.read_text(encoding="utf-8").splitlines()
    entry_keys = set(entries)
    blocks_by_entry = {}
    call_names_by_entry = {}
    unresolved = []

    for i, line in enumerate(lines):
        target = _call_target(line)
        if target is None:
            continue
        resolved = _resolve_target(target, entry_keys)
        if resolved is None:
            if not _is_external_target(target):
                unresolved.append(target)
            continue
        blocks_by_entry.setdefault(resolved, []).append(_call_block(lines, i))
        call_names_by_entry.setdefault(resolved, set()).add(target)

    if unresolved:
        raise ValueError(
            "unresolved non-external flow call targets in "
            f"{flow_path.name}: {sorted(set(unresolved))}"
        )

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
    return refs

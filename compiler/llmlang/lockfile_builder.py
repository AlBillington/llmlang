"""Builds a lockfile: hashes every source-handled entry's combined bullets and
located code, every class/file-level bullet group's combined bullets,
and every policy's text. Class-level bullet groups and policies have no
code location of their own, so they're tracked with text_hash only.

Two entry points:
- build() is the plain, unguarded path - hashes whatever's currently
  there and writes it, no comparison to any prior state, no awareness
  of dispositions at all. For bootstrapping a brand new lockfile, or a
  human directly supervising their own paired edit.
- finalize() is the guarded incremental path - see its own docstring.
"""
import hashlib
import json
from pathlib import Path

from llmlang.extractor import (
    extract_by_handle,
    test_comment_base,
    test_comment_roots,
    test_comments_by_node,
)
from llmlang.flow import flow_path_for_llmlang, generate_flow_for_tree
from llmlang.lockfile import LOCKFILE_SCHEMA_VERSION, RULESET_VERSION
from llmlang.lockfile_checker import check
from llmlang.parser import (
    applicable_policy_text,
    parse,
    walk_class_bullet_groups,
    walk_entries,
    walk_policies,
    walk_tests,
)


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _combined(bullets: list) -> str:
    return "\n".join(bullets)


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _hash_all_entries(llmlang_path: Path, root) -> dict:
    """tracking_key -> (file_rel, text, text_hash, code_hash, spec_hash) for
    every source-handled entry, computed fresh from the current llmlang text, current
    code, and every policy currently covering it - never from any prior
    lockfile. spec_hash folds the entry's own text together with every
    applicable policy's text, so it moves if either one does; when nothing
    covers the entry it reduces to exactly text_hash."""
    result = {}
    for file_rel, handle_key, tracking_key, bullets, _entry_line in walk_entries(root):
        text = _combined(bullets)
        file_path = llmlang_path.parent / file_rel
        found = extract_by_handle(file_path, handle_key)
        if found is None:
            print(f"WARNING: no handle [llm:{handle_key}] found for {tracking_key} in {file_rel}")
            continue
        code, _code_line = found
        policy_texts = applicable_policy_text(root, file_rel)
        spec_hash = _sha256("\n".join([text] + policy_texts))
        result[tracking_key] = (file_rel, text, _sha256(text), _sha256(code), spec_hash)
    return result


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _policies_and_class_bullets(root) -> tuple:
    policies = {}
    for scope, i, text in walk_policies(root):
        scope_str = ".".join(scope) if scope else "root"
        policies.setdefault(scope_str, {})
        policies[scope_str][f"policy[{i}]"] = {"text": text, "text_hash": _sha256(text)}

    class_bullets = {}
    for tracking_key, sibling_keys, bullets, _class_line in walk_class_bullet_groups(root):
        text = _combined(bullets)
        class_bullets[tracking_key] = {
            "text": text,
            "text_hash": _sha256(text),
            "depends_on": sibling_keys,
        }
    return policies, class_bullets


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _test_comment_lookup(llmlang_path: Path):
    return test_comments_by_node(
        test_comment_roots(llmlang_path),
        base_path=test_comment_base(llmlang_path),
    )


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _test_trace_record(comment) -> dict:
    return {
        "text": comment.text,
        "path": comment.path,
        "code_hash": comment.code_hash,
    }


# private helper of build()/finalize(), not independent architecture [llm-exempt]
def _test_traces(llmlang_path: Path, root) -> dict:
    comments = _test_comment_lookup(llmlang_path)
    traces = {}
    stale_comments = [
        (canonical_name, comment.text)
        for canonical_name, comments_for_node in comments.items()
        for comment in comments_for_node
    ]
    expected_tests = set(walk_tests(root))
    stale_comments = [
        (canonical_name, test_text)
        for canonical_name, test_text in stale_comments
        if (canonical_name, test_text) not in expected_tests
    ]
    if stale_comments:
        details = "\n".join(
            f"- {canonical_name}: {test_text}" for canonical_name, test_text in stale_comments
        )
        raise ValueError("stale llm-test comments without matching test bullets:\n" + details)

    missing = []
    for canonical_name, test_text in walk_tests(root):
        matches = [
            comment for comment in comments.get(canonical_name, []) if comment.text == test_text
        ]
        if not matches:
            missing.append((canonical_name, test_text))
    if missing:
        details = "\n".join(
            f"- {canonical_name}: {test_text}" for canonical_name, test_text in missing
        )
        raise ValueError("missing llm-test comments for test bullets:\n" + details)
    for canonical_name, test_text in walk_tests(root):
        matches = [
            comment for comment in comments.get(canonical_name, []) if comment.text == test_text
        ]
        traces.setdefault(canonical_name, []).extend(_test_trace_record(match) for match in matches)
    return traces


# refuses to write a lockfile or flow file when an entry's own → call line doesn't resolve [llm-exempt]
def _write_flow_or_raise(llmlang_path: Path, root):
    text, errors = generate_flow_for_tree(root)
    if errors:
        flow_name = flow_path_for_llmlang(llmlang_path).name
        details = "\n".join(f"- {e['source']}: {e['message']}" for e in errors)
        raise ValueError(f"flow call errors while generating {flow_name}:\n{details}")
    flow_path = flow_path_for_llmlang(llmlang_path)
    if text:
        flow_path.write_text(text, encoding="utf-8")
    elif flow_path.exists():
        flow_path.unlink()


# builds a lockfile by using Parser to read llmlang, Extractor to locate each entry's code, and Lockfile to record a text and code hash per entry [llm:llmlang.lockfile_builder.build]
def build(llmlang_path: Path, lockfile_path: Path):
    root = parse(llmlang_path)
    test_traces = _test_traces(llmlang_path, root)
    hashed = _hash_all_entries(llmlang_path, root)
    policies, class_bullets = _policies_and_class_bullets(root)
    _write_flow_or_raise(llmlang_path, root)

    lock = {
        "lockfile_schema_version": LOCKFILE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "policies": policies,
        "entries": {
            key: {"file": file_rel, "text": text, "text_hash": text_hash, "code_hash": code_hash}
            for key, (file_rel, text, text_hash, code_hash, _spec_hash) in hashed.items()
        },
        "class_bullets": class_bullets,
        "test_traces": test_traces,
    }
    lockfile_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    return lock


# guards an incremental rebuild against silently skipping a flagged entry, reading and updating a change manifest bound to the exact spec and code hashes it describes [llm:llmlang.lockfile_builder.finalize]
def finalize(llmlang_path: Path, lockfile_path: Path, changes_path: Path):
    ok, flagged_entries, findings = check(llmlang_path, lockfile_path)
    if not ok and not flagged_entries:
        for finding in findings:
            print(finding.message)
        raise ValueError(
            "finalize refused: no valid lockfile to check against "
            "(missing, or schema out of date) - bootstrap with a plain rebuild first"
        )
    if findings:
        print("Currently flagged (a disposition is required for each to finalize):")
        for finding in findings:
            print(f"  {finding.message}")

    changes = json.loads(changes_path.read_text(encoding="utf-8")) if changes_path.exists() else {}

    root = parse(llmlang_path)
    test_traces = _test_traces(llmlang_path, root)
    hashed = _hash_all_entries(llmlang_path, root)
    policies, class_bullets = _policies_and_class_bullets(root)
    _write_flow_or_raise(llmlang_path, root)

    new_changes = {}
    resolved = {}
    for key, value in changes.items():
        if key in hashed:
            _, _, _, code_hash, spec_hash = hashed[key]
            if isinstance(value, dict):
                if value.get("for_spec_hash") == spec_hash and value.get("for_code_hash") == code_hash:
                    # still describes exactly the current state - keep it
                    new_changes[key] = value
                    resolved[key] = value
                # else: stale - the entry or an applicable policy moved on since this was recorded, drop it
            elif isinstance(value, str) and value:
                # fresh submission - stamp it against the current state
                stamped = {"disposition": value, "for_spec_hash": spec_hash, "for_code_hash": code_hash}
                new_changes[key] = stamped
                resolved[key] = stamped
            # else: empty or malformed value, drop it
            continue
        # orphaned - this entry no longer exists

    missing = flagged_entries - resolved.keys()
    if missing:
        raise ValueError(
            f"finalize refused: no disposition given for currently flagged entries: {sorted(missing)}"
        )

    lock = {
        "lockfile_schema_version": LOCKFILE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "policies": policies,
        "entries": {},
        "class_bullets": class_bullets,
        "test_traces": test_traces,
    }
    for key, (file_rel, text, text_hash, code_hash, _spec_hash) in hashed.items():
        entry_record = {"file": file_rel, "text": text, "text_hash": text_hash, "code_hash": code_hash}
        if key in resolved:
            entry_record["last_change"] = resolved[key]
        lock["entries"][key] = entry_record

    lockfile_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    changes_path.write_text(json.dumps(new_changes, indent=2), encoding="utf-8")
    return lock

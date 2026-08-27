"""Checks a lockfile against the current llmlang and code.

Every flagged entry is one of two kinds:
  - SPEC_DIVERGED: the llmlang side moved since the last build - the
    entry's own bullets changed, it's brand new, or an upstream
    @policy: covering it changed. Safe default: update the code to
    satisfy what's currently written.
  - CODE_DIVERGED: the code side moved with no corresponding spec
    change to explain it (handle missing, or its hash just doesn't
    match). Not safe to blindly regenerate - investigate first, since
    this usually means something broke rather than an intentional
    change nobody documented.

Cascades in two ways:
  - Policy -> entries: if a policy's text changed, every entry within
    that policy's scope gets flagged SPEC_DIVERGED even if its own
    text/code hashes still match. Root-scope policies affect
    everything; folder/file/class-scope policies affect everything
    nested beneath them.
  - Entry -> class bullets: a class/file-level bullet group (spanning
    more than one entry) gets flagged SPEC_DIVERGED whenever any entry
    it depends on was flagged for any reason.
"""
import hashlib
import json
from pathlib import Path

from Compiler.Extractor import (
    extract_by_handle,
    test_comment_base,
    test_comment_roots,
    test_comments_by_node,
)
from Compiler.Lockfile import LOCKFILE_SCHEMA_VERSION, RULESET_VERSION
from Compiler.Parser import (
    parse,
    policy_in_scope,
    walk_class_bullet_groups,
    walk_entries,
    walk_test_lines,
    walk_tests,
    walk_policies,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _combined(bullets: list) -> str:
    return "\n".join(bullets)


def _test_comment_lookup(llmlang_path: Path):
    return test_comments_by_node(
        test_comment_roots(llmlang_path),
        base_path=test_comment_base(llmlang_path),
    )


def _trace_location(canonical_name: str, text: str, path: str, line: int | None = None) -> str:
    loc = f"{path}:{line}" if line else path
    return f"{canonical_name} — {loc} — {text}"


def _check_test_traces(llmlang_path: Path, root, lock: dict) -> tuple[bool, set, list]:
    ok = True
    flagged = set()
    findings = []
    comments = _test_comment_lookup(llmlang_path)
    expected_tests = set(walk_tests(root))
    test_line_by_pair = {
        (canonical_name, test_text): line for canonical_name, test_text, line in walk_test_lines(root)
    }
    current_traces = [
        (canonical_name, comment.text, comment.path, comment.line, comment.code_hash)
        for canonical_name, comments_for_node in comments.items()
        for comment in comments_for_node
    ]
    current_text_paths = {
        (canonical_name, text, path) for canonical_name, text, path, _line, _code_hash in current_traces
    }
    current_texts = {(canonical_name, text) for canonical_name, text, _path, _line, _hash in current_traces}

    for canonical_name, test_text in expected_tests:
        if (canonical_name, test_text) not in current_texts:
            line = test_line_by_pair.get((canonical_name, test_text))
            loc = f"{llmlang_path}:{line}" if line else str(llmlang_path)
            findings.append(f"TEST_LINK_MISSING: {canonical_name} — {test_text} ({loc})")
            ok = False
            flagged.add(canonical_name)

    for canonical_name, test_text, path, line, code_hash in current_traces:
        if (canonical_name, test_text) not in expected_tests:
            findings.append(f"TEST_TRACE_STALE: {_trace_location(canonical_name, test_text, path, line)}")
            ok = False
            flagged.add(canonical_name)
            continue
        locked_matches = [
            trace
            for trace in lock.get("test_traces", {}).get(canonical_name, [])
            if trace.get("text") == test_text and trace.get("path") == path
        ]
        if not locked_matches:
            findings.append(
                f"TEST_TRACE_DIVERGED (new or moved test trace): {path}:{line} — {canonical_name}"
            )
            ok = False
            flagged.add(canonical_name)
            continue
        if not any(trace.get("code_hash") == code_hash for trace in locked_matches):
            findings.append(f"TEST_CODE_DIVERGED: {_trace_location(canonical_name, test_text, path, line)}")
            ok = False
            flagged.add(canonical_name)

    for canonical_name, traces in lock.get("test_traces", {}).items():
        for trace in traces:
            test_text = trace.get("text", "")
            path = trace.get("path", "")
            if (canonical_name, test_text, path) in current_text_paths:
                continue
            if (canonical_name, test_text) in expected_tests:
                llm_line = test_line_by_pair.get((canonical_name, test_text))
                loc = f"{llmlang_path}:{llm_line}" if llm_line else path
                findings.append(
                    "TEST_TRACE_DIVERGED (locked test trace missing): "
                    f"{canonical_name} — {loc} — {test_text}"
                )
                ok = False
                flagged.add(canonical_name)

    return ok, flagged, findings


# checks a lockfile by using Parser and Extractor to compare current text and code hashes against Lockfile, reporting each entry as SPEC_DIVERGED, CODE_DIVERGED, or unchanged, alongside its file and line [llm:Compiler.LockfileChecker.check]
def check(llmlang_path: Path, lockfile_path: Path) -> tuple:
    if not lockfile_path.exists():
        return False, set(), ["No lockfile found."]

    lock = json.loads(lockfile_path.read_text(encoding="utf-8"))

    if lock.get("lockfile_schema_version") != LOCKFILE_SCHEMA_VERSION:
        return False, set(), [
            f"Lockfile schema is out of date (found "
            f"{lock.get('lockfile_schema_version')!r}, expected {LOCKFILE_SCHEMA_VERSION}). "
            f"Rebuild it."
        ]

    root = parse(llmlang_path)
    ok = True
    findings = []
    changed_policy_scopes = []
    flagged_entries = set()
    test_traces_ok, flagged_test_traces, test_trace_findings = _check_test_traces(llmlang_path, root, lock)
    if not test_traces_ok:
        ok = False
        flagged_entries.update(flagged_test_traces)
        findings.extend(test_trace_findings)

    if lock.get("ruleset_version") != RULESET_VERSION:
        findings.append(
            f"RULESET CHANGED (was {lock.get('ruleset_version')!r}, now "
            f"{RULESET_VERSION!r}), review affected entries: root"
        )
        ok = False
        changed_policy_scopes.append(())

    for scope, i, text in walk_policies(root):
        scope_str = ".".join(scope) if scope else "root"
        entry = lock.get("policies", {}).get(scope_str, {}).get(f"policy[{i}]")
        if entry is None:
            findings.append(f"MISSING in lockfile: {scope_str}.policy[{i}]")
            ok = False
            changed_policy_scopes.append(scope)
            continue
        if _sha256(text) != entry["text_hash"]:
            findings.append(f"POLICY CHANGED, review affected entries: {scope_str}.policy[{i}]")
            ok = False
            changed_policy_scopes.append(scope)

    for file_rel, handle_key, tracking_key, bullets, entry_line in walk_entries(root):
        text = _combined(bullets)
        entry = lock.get("entries", {}).get(tracking_key)
        llm_loc = f"{llmlang_path}:{entry_line}"

        if entry is None:
            findings.append(f"SPEC_DIVERGED (new entry, not yet in lockfile): {tracking_key} [llm:{handle_key}] — {llm_loc}")
            ok = False
            flagged_entries.add(tracking_key)
            continue

        if _sha256(text) != entry["text_hash"]:
            findings.append(f"SPEC_DIVERGED (bullets changed since last build): {tracking_key} [llm:{handle_key}] — {llm_loc}")
            ok = False
            flagged_entries.add(tracking_key)
            continue

        file_path = llmlang_path.parent / file_rel
        found = extract_by_handle(file_path, handle_key)
        if found is None:
            findings.append(f"CODE_DIVERGED (handle [llm:{handle_key}] not found): {tracking_key} — {file_rel}")
            ok = False
            flagged_entries.add(tracking_key)
            continue
        code, code_line = found
        code_loc = f"{file_rel}:{code_line}"
        if _sha256(code) != entry["code_hash"]:
            findings.append(f"CODE_DIVERGED (code changed unexpectedly): {tracking_key} — {code_loc}")
            ok = False
            flagged_entries.add(tracking_key)
        elif any(policy_in_scope(scope, file_rel) for scope in changed_policy_scopes):
            findings.append(f"SPEC_DIVERGED (upstream policy changed): {tracking_key} — {llm_loc}")
            ok = False
            flagged_entries.add(tracking_key)

    for tracking_key, sibling_keys, bullets, class_line in walk_class_bullet_groups(root):
        text = _combined(bullets)
        entry = lock.get("class_bullets", {}).get(tracking_key)
        llm_loc = f"{llmlang_path}:{class_line}"

        if entry is None:
            findings.append(f"SPEC_DIVERGED (new class-level bullet, not yet in lockfile): {tracking_key} — {llm_loc}")
            ok = False
            continue

        if _sha256(text) != entry["text_hash"]:
            findings.append(f"SPEC_DIVERGED (bullets changed since last build): {tracking_key} (class-level) — {llm_loc}")
            ok = False
            continue

        if any(key in flagged_entries for key in sibling_keys):
            findings.append(f"SPEC_DIVERGED (an entry it depends on changed): {tracking_key} (class-level) — {llm_loc}")
            ok = False

    return ok, flagged_entries, findings

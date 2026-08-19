"""Checks a lockfile against the current llmlang and code.

Cascades in two ways:
  - Policy -> entries: if a policy's text changed, every entry within
    that policy's scope gets flagged NEEDS REVIEW even if its own
    text/code hashes still match. Root-scope policies affect
    everything; folder/file/class-scope policies affect everything
    nested beneath them.
  - Entry -> class bullets: a class/file-level bullet group (spanning
    more than one entry) gets flagged NEEDS REVIEW whenever any entry
    it depends on was flagged for any reason.
"""
import hashlib
import json
from pathlib import Path

from Compiler.Extractor import extract_by_handle
from Compiler.Lockfile import LOCKFILE_SCHEMA_VERSION, RULESET_VERSION
from Compiler.Parser import parse, walk_class_bullet_groups, walk_entries, walk_policies


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _combined(bullets: list) -> str:
    return "\n".join(bullets)


def _policy_in_scope(policy_scope: tuple, entry_file: str) -> bool:
    """A policy at scope ('a','b') covers an entry whose file lives under
    folder path a/b/... (root scope, empty tuple, covers everything)."""
    if not policy_scope:
        return True
    prefix = "/".join(policy_scope)
    return entry_file == prefix or entry_file.startswith(prefix + "/") or entry_file.startswith(prefix + ".")


# checks a lockfile by using Parser and Extractor to compare current text and code hashes against Lockfile, reporting each entry as dirty, missing or corrupt, or unchanged, and returns the set of named-entry tracking keys currently flagged for any reason [llm:check]
def check(llmlang_path: Path, lockfile_path: Path) -> tuple:
    if not lockfile_path.exists():
        print("No lockfile found.")
        return False, set()

    lock = json.loads(lockfile_path.read_text())

    if lock.get("lockfile_schema_version") != LOCKFILE_SCHEMA_VERSION:
        print(
            f"Lockfile schema is out of date (found "
            f"{lock.get('lockfile_schema_version')!r}, expected {LOCKFILE_SCHEMA_VERSION}). "
            f"Rebuild it."
        )
        return False, set()

    root = parse(llmlang_path)
    ok = True
    changed_policy_scopes = []
    flagged_entries = set()

    if lock.get("ruleset_version") != RULESET_VERSION:
        print(
            f"RULESET CHANGED (was {lock.get('ruleset_version')!r}, now "
            f"{RULESET_VERSION!r}), review affected entries: root"
        )
        ok = False
        changed_policy_scopes.append(())

    for scope, i, text in walk_policies(root):
        scope_str = ".".join(scope) if scope else "root"
        entry = lock.get("policies", {}).get(scope_str, {}).get(f"policy[{i}]")
        if entry is None:
            print(f"MISSING in lockfile: {scope_str}.policy[{i}]")
            ok = False
            changed_policy_scopes.append(scope)
            continue
        if _sha256(text) != entry["text_hash"]:
            print(f"POLICY CHANGED, review affected entries: {scope_str}.policy[{i}]")
            ok = False
            changed_policy_scopes.append(scope)

    for file_rel, handle_key, tracking_key, bullets in walk_entries(root):
        text = _combined(bullets)
        entry = lock.get("entries", {}).get(tracking_key)

        if entry is None:
            print(f"MISSING in lockfile: {tracking_key}")
            ok = False
            flagged_entries.add(tracking_key)
            continue

        if _sha256(text) != entry["text_hash"]:
            print(f"DIRTY (spec changed, needs recompile): {tracking_key}")
            ok = False
            flagged_entries.add(tracking_key)
            continue

        file_path = llmlang_path.parent / file_rel
        code = extract_by_handle(file_path, handle_key)
        if code is None:
            print(f"MISSING/CORRUPT (handle [llm:{handle_key}] not found): {tracking_key}")
            ok = False
            flagged_entries.add(tracking_key)
        elif _sha256(code) != entry["code_hash"]:
            print(f"MISSING/CORRUPT (code changed unexpectedly): {tracking_key}")
            ok = False
            flagged_entries.add(tracking_key)
        elif any(_policy_in_scope(scope, file_rel) for scope in changed_policy_scopes):
            print(f"NEEDS REVIEW (upstream policy changed): {tracking_key}")
            ok = False
            flagged_entries.add(tracking_key)

    for tracking_key, sibling_keys, bullets in walk_class_bullet_groups(root):
        text = _combined(bullets)
        entry = lock.get("class_bullets", {}).get(tracking_key)

        if entry is None:
            print(f"MISSING in lockfile: {tracking_key} (class-level)")
            ok = False
            continue

        if _sha256(text) != entry["text_hash"]:
            print(f"DIRTY (spec changed, needs recompile): {tracking_key} (class-level)")
            ok = False
            continue

        if any(key in flagged_entries for key in sibling_keys):
            print(f"NEEDS REVIEW (an entry it depends on changed): {tracking_key} (class-level)")
            ok = False

    if ok:
        print("OK — lockfile matches llmlang and code.")
    return ok, flagged_entries

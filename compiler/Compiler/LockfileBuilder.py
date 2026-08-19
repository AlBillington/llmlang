"""Builds a lockfile: hashes every named entry's combined bullets and
located code, every class/file-level bullet group's combined bullets,
and every policy's text. Class-level bullet groups and policies have no
code location of their own, so they're tracked with text_hash only.

A build may optionally be given a change manifest - {tracking_key: "free
text describing what changed, or why nothing needed to"} - covering a
round of edits. When one is given, every named entry Checker currently
flags (DIRTY, MISSING/CORRUPT, or NEEDS REVIEW) must have a non-empty
entry in it, or the build refuses outright and lists exactly which keys
are missing, rather than silently accepting an entry nobody actually
looked at. This only guarantees every flagged entry was *addressed* -
it says nothing about whether the disposition given is true; that's
still a human-review question, same as everything else generated code
isn't automatically trusted for.

An accepted disposition is stored bound to the exact text_hash/code_hash
it was recorded against, not as a bare string - so a later unguarded
rebuild that lets an entry drift again can't silently carry the old
disposition forward next to hashes it was never actually about. A
carried-forward disposition is only kept when both hashes still match
what they were when it was written; otherwise it's dropped rather than
misrepresented as still describing the current state."""
import hashlib
import json
from pathlib import Path

from Compiler.Extractor import extract_by_handle
from Compiler.Lockfile import LOCKFILE_SCHEMA_VERSION, RULESET_VERSION
from Compiler.LockfileChecker import check
from Compiler.Parser import parse, walk_class_bullet_groups, walk_entries, walk_policies


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _combined(bullets: list) -> str:
    return "\n".join(bullets)


# builds a lockfile by using Parser to read llmlang, Extractor to locate each entry's code, and Lockfile to record a text and code hash per entry, optionally requiring a change manifest covering every currently flagged entry first [llm:build]
def build(llmlang_path: Path, lockfile_path: Path, manifest: dict = None):
    if manifest is not None:
        ok, flagged_entries = check(llmlang_path, lockfile_path)
        if not ok and not flagged_entries:
            raise ValueError(
                "finalize refused: no valid lockfile to check against "
                "(missing, or schema out of date) - bootstrap with a plain rebuild first"
            )
        missing = flagged_entries - {k for k, v in manifest.items() if v}
        if missing:
            raise ValueError(
                f"finalize refused: no disposition given for currently flagged entries: {sorted(missing)}"
            )

    old_lock = json.loads(lockfile_path.read_text()) if lockfile_path.exists() else {}

    root = parse(llmlang_path)
    lock = {
        "lockfile_schema_version": LOCKFILE_SCHEMA_VERSION,
        "ruleset_version": RULESET_VERSION,
        "policies": {},
        "entries": {},
        "class_bullets": {},
    }

    for scope, i, text in walk_policies(root):
        scope_str = ".".join(scope) if scope else "root"
        lock["policies"].setdefault(scope_str, {})
        lock["policies"][scope_str][f"policy[{i}]"] = {"text": text, "text_hash": _sha256(text)}

    for file_rel, handle_key, tracking_key, bullets in walk_entries(root):
        text = _combined(bullets)
        file_path = llmlang_path.parent / file_rel
        code = extract_by_handle(file_path, handle_key)
        if code is None:
            print(f"WARNING: no handle [llm:{handle_key}] found for {tracking_key} in {file_rel}")
            continue
        text_hash = _sha256(text)
        code_hash = _sha256(code)
        entry_record = {
            "file": file_rel,
            "text": text,
            "text_hash": text_hash,
            "code_hash": code_hash,
        }
        if manifest is not None and manifest.get(tracking_key):
            entry_record["last_change"] = {
                "disposition": manifest[tracking_key],
                "for_text_hash": text_hash,
                "for_code_hash": code_hash,
            }
        else:
            prior = old_lock.get("entries", {}).get(tracking_key, {}).get("last_change")
            if (
                isinstance(prior, dict)
                and prior.get("for_text_hash") == text_hash
                and prior.get("for_code_hash") == code_hash
            ):
                # still describes exactly this state - carry it forward
                entry_record["last_change"] = prior
            # else: hashes moved since this disposition was recorded (most
            # likely via an unguarded plain rebuild) - drop it rather than
            # silently re-stamp a claim next to state it no longer describes
        lock["entries"][tracking_key] = entry_record

    for tracking_key, sibling_keys, bullets in walk_class_bullet_groups(root):
        text = _combined(bullets)
        lock["class_bullets"][tracking_key] = {
            "text": text,
            "text_hash": _sha256(text),
            "depends_on": sibling_keys,
        }

    lockfile_path.write_text(json.dumps(lock, indent=2))
    return lock

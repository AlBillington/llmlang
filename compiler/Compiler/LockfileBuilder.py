"""Builds a lockfile: hashes every named entry's combined bullets and
located code, every class/file-level bullet group's combined bullets,
and every policy's text. Class-level bullet groups and policies have no
code location of their own, so they're tracked with text_hash only."""
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


# builds a lockfile by using Parser to read llmlang, Extractor to locate each entry's code, and Lockfile to record a text and code hash per entry [llm:build]
def build(llmlang_path: Path, lockfile_path: Path):
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
        lock["entries"][tracking_key] = {
            "file": file_rel,
            "text": text,
            "text_hash": _sha256(text),
            "code_hash": _sha256(code),
        }

    for tracking_key, sibling_keys, bullets in walk_class_bullet_groups(root):
        text = _combined(bullets)
        lock["class_bullets"][tracking_key] = {
            "text": text,
            "text_hash": _sha256(text),
            "depends_on": sibling_keys,
        }

    lockfile_path.write_text(json.dumps(lock, indent=2))
    return lock

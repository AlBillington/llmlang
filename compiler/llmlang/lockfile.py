"""Lockfile entry shape and versioning used by LockfileBuilder and LockfileChecker."""
from dataclasses import dataclass
from typing import TypedDict


# stores, per source-handled entry, its file, text hash, and code hash [llm:llmlang.lockfile.LockEntry]
class LockEntry(TypedDict, total=False):
    file: str
    text: str
    text_hash: str
    code_hash: str


# stores, per linked test comment, the explanation text and backing code hash [llm:llmlang.lockfile.TestTrace]
class TestTrace(TypedDict, total=False):
    text: str
    path: str
    code_hash: str


# stores, per flow reference, the connected llmlang entry hash, code hash, and flow-block hash [llm:llmlang.lockfile.FlowRef]
class FlowRef(TypedDict, total=False):
    flow: str
    entry: str
    call_names: list[str]
    entry_spec_hash: str
    code_hash: str
    flow_ref_hash: str


# stores one check/coverage failure as structured data, not just display text [llm:llmlang.lockfile.Finding]
@dataclass
class Finding:
    category: str
    message: str
    file: str | None = None
    line: int | None = None


# the lockfile's own schema version, bumped whenever its shape changes [llm:llmlang.lockfile.LOCKFILE_SCHEMA_VERSION]
LOCKFILE_SCHEMA_VERSION = 5

# the ruleset version every entry in a lockfile is built under together [llm:llmlang.lockfile.RULESET_VERSION]
RULESET_VERSION = "2026-08-21-flow-ref-triples"

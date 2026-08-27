"""Lockfile entry shape and versioning used by LockfileBuilder and LockfileChecker."""
from dataclasses import dataclass
from typing import TypedDict


# stores, per source-handled entry, its file, text hash, and code hash [llm:Compiler.Lockfile.LockEntry]
class LockEntry(TypedDict, total=False):
    file: str
    text: str
    text_hash: str
    code_hash: str


# stores, per linked test comment, the explanation text and backing code hash [llm:Compiler.Lockfile.TestTrace]
class TestTrace(TypedDict, total=False):
    text: str
    path: str
    code_hash: str


# stores one check/coverage failure as structured data, not just display text [llm:Compiler.Lockfile.Finding]
@dataclass
class Finding:
    category: str
    message: str
    file: str | None = None
    line: int | None = None


# the lockfile's own schema version, bumped whenever its shape changes [llm:Compiler.Lockfile.LOCKFILE_SCHEMA_VERSION]
LOCKFILE_SCHEMA_VERSION = 4

# the ruleset version every entry in a lockfile is built under together [llm:Compiler.Lockfile.RULESET_VERSION]
RULESET_VERSION = "2026-08-20-hash-only-test-traces"

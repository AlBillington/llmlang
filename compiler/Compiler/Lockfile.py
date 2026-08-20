"""Lockfile entry shape and versioning used by LockfileBuilder and LockfileChecker."""
from typing import TypedDict


# stores, per named entry, its file, text hash, and code hash [llm:Compiler.Lockfile.LockEntry]
class LockEntry(TypedDict, total=False):
    file: str
    text: str
    text_hash: str
    code_hash: str


# the lockfile's own schema version, bumped whenever its shape changes [llm:Compiler.Lockfile.LOCKFILE_SCHEMA_VERSION]
LOCKFILE_SCHEMA_VERSION = 2

# the ruleset version every entry in a lockfile is built under together [llm:Compiler.Lockfile.RULESET_VERSION]
RULESET_VERSION = "2026-08-20-test-trace"

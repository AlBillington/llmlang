"""Lockfile entry shape and versioning used by LockfileBuilder and LockfileChecker."""
from typing import TypedDict


# stores, per named entry, its file, text hash, and code hash [llm:LockEntry]
class LockEntry(TypedDict, total=False):
    file: str
    text: str
    text_hash: str
    code_hash: str


# the lockfile's own schema version, bumped whenever its shape changes [llm:LOCKFILE_SCHEMA_VERSION]
LOCKFILE_SCHEMA_VERSION = 2

# the ruleset version every entry in a lockfile is built under together [llm:RULESET_VERSION]
RULESET_VERSION = "2026-08-15"

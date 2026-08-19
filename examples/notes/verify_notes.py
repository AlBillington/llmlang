"""Ad-hoc verification of the "should" bullets against the real legacy
code. Not part of the permanent test suite - just proving the llmlang's
claims are actually true before treating it as onboarded."""
from legacy_app.notes import NotesStore, NotesValidator

store = NotesStore()
note_id = store.add_note("buy milk")
assert isinstance(note_id, str) and note_id

assert "buy milk" in store.list_notes(), "should include a note that was added, when listing all notes"

validator = NotesValidator()
assert not validator.is_valid("") and not validator.is_valid("   ")
assert validator.is_valid("buy milk")

print("All proposed claims hold against the real code.")

"""Ad-hoc verification of the test bullets against the real legacy code."""
from legacy_app.notes import NotesStore, NotesValidator

store = NotesStore()
note_id = store.add_note("buy milk")
assert isinstance(note_id, str) and note_id

# should include a note that was added, when listing all notes [llm-test:legacy_app.notes.NotesStore]
assert "buy milk" in store.list_notes(), "should include a note that was added, when listing all notes"

validator = NotesValidator()
# should reject empty and whitespace-only note text [llm-test:legacy_app.notes.NotesValidator.is_valid]
assert not validator.is_valid("") and not validator.is_valid("   ")
# should accept non-empty note text [llm-test:legacy_app.notes.NotesValidator.is_valid]
assert validator.is_valid("buy milk")

print("All proposed claims hold against the real code.")

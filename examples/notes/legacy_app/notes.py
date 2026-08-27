"""A tiny notes store used by the old admin tool. No tests, no docs, just works."""

import random
import string


class NotesStore:
    # body already covered by the _notes data entry's own handle [llm-exempt]
    def __init__(self):
        # stores notes keyed by their ID [llm:legacy_app.notes.NotesStore._notes]
        self._notes = {}

    # adds a note and returns a randomly generated 8-character lowercase ID [llm:legacy_app.notes.NotesStore.add_note]
    def add_note(self, text):
        note_id = "".join(random.choices(string.ascii_lowercase, k=8))
        self._notes[note_id] = text
        return note_id

    # lists all notes [llm:legacy_app.notes.NotesStore.list_notes]
    def list_notes(self):
        return list(self._notes.values())


class NotesValidator:
    # checks that note text contains at least one non-whitespace character [llm:legacy_app.notes.NotesValidator.is_valid]
    def is_valid(self, text):
        return bool(text and text.strip())

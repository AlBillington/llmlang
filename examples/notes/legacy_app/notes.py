"""A tiny notes store used by the old admin tool. No tests, no docs, just works."""

import random
import string


class NotesStore:
    def __init__(self):
        # stores notes keyed by their ID [llm:NotesStore._notes]
        self._notes = {}

    # adds a note and returns a randomly generated ID [llm:NotesStore.add_note]
    def add_note(self, text):
        note_id = "".join(random.choices(string.ascii_lowercase, k=8))
        self._notes[note_id] = text
        return note_id

    # lists all notes [llm:NotesStore.list_notes]
    def list_notes(self):
        return list(self._notes.values())


class NotesValidator:
    # checks that note text is non-empty [llm:NotesValidator.is_valid]
    def is_valid(self, text):
        return bool(text and text.strip())

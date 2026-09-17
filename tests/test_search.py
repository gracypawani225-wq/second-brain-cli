from brain.db import BrainDB


def test_fts_search_finds_relevant_notes(tmp_path):
    db = BrainDB(tmp_path / "brain.db")
    matching = db.add_note("A hash table provides fast average lookup.", ["dsa"])
    db.add_note("TCP guarantees ordered delivery of packets.", ["networking"])

    results = db.search_notes("fast lookup")

    assert [note.id for note in results] == [matching.id]


def test_search_handles_punctuation_and_empty_terms(tmp_path):
    db = BrainDB(tmp_path / "brain.db")
    matching = db.add_note("Python uses a simple syntax.")

    assert [note.id for note in db.search_notes("Python!")] == [matching.id]
    assert db.search_notes("... !!!") == []

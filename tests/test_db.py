from brain.db import BrainDB


def test_add_get_list_and_delete_notes(tmp_path):
    db = BrainDB(tmp_path / "brain.db")
    saved = db.add_note("Binary search is O(log n).", ["Algorithms", "DSA", "algorithms"])

    assert saved.id == 1
    assert saved.tags == ("algorithms", "dsa")
    assert db.get_note(saved.id).text == "Binary search is O(log n)."
    assert [note.id for note in db.list_notes("ALGORITHMS")] == [saved.id]
    assert db.delete_note(saved.id) is True
    assert db.get_note(saved.id) is None
    assert db.delete_note(saved.id) is False
    assert db.stats().most_used_tags == ()


def test_stats_reports_notes_and_tags(tmp_path):
    db = BrainDB(tmp_path / "brain.db")
    first = db.add_note("A process has its own memory space.", ["os"])
    second = db.add_note("Threads share process memory.", ["os", "concurrency"])

    stats = db.stats()

    assert stats.total_notes == 2
    assert stats.notes_this_week == 2
    assert stats.most_used_tags[0] == ("os", 2)
    assert stats.oldest_note.id == first.id
    assert stats.newest_note.id == second.id

# second-brain-cli

A tiny, local-first second brain for the terminal. Capture a thought in seconds, retrieve it later with SQLite full-text search, and optionally ask Gemini questions grounded only in your saved notes.

No cloud database. No vector database. No framework maze. Your notes live in `~/.second-brain/brain.db`.

## Features

- Save notes with repeatable tags
- List and filter notes in a clean terminal table
- Search locally with SQLite FTS5 — no API key required
- Read or safely delete a specific note
- See useful brain stats
- Optionally ask Gemini questions using matching notes as traceable context

## Quick start

Requires Python 3.11 or later.

```bash
git clone https://github.com/gracypawani225-wq/second-brain-cli.git
cd second-brain-cli
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

brain add "A hash table gives average O(1) lookup using a hash function." --tag algorithms --tag dsa
brain add "TCP guarantees ordered delivery of packets." --tag networking
brain search "fast lookup"
brain list --tag algorithms
brain stats
```

## Commands

| Command | What it does |
| --- | --- |
| `brain add "..." --tag name` | Save a note; repeat `--tag` as needed. |
| `brain list [--tag name]` | List every note, optionally filtered by tag. |
| `brain search "words"` | Find relevant notes with local FTS5 search. |
| `brain show ID` | Display one note and all its metadata. |
| `brain delete ID [--yes]` | Delete a note after confirmation; `--yes` skips it. |
| `brain stats` | Show note count, recent activity, popular tags, and note age. |
| `brain ask "question"` | Ask Gemini about the matching saved notes. |

For development and automated tests, commands also accept a hidden `--db /path/to/test.db` option, keeping test data separate from your real notes.

## Optional AI answers

The core app works fully offline. To enable `brain ask`, install the optional dependency and set a Gemini key:

```bash
pip install -e ".[ai]"
export GEMINI_API_KEY="your_key_here"
brain ask "When should I use a hash table?"
```

`brain ask` first finds the most relevant local notes, sends only those notes with the question to Gemini, and tells Gemini not to use outside information. It prints the note IDs used so each answer is traceable. If there are no matching notes, it says there is not enough saved information rather than calling the model.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The project intentionally has a small shape:

```text
brain/
  cli.py    # Typer + Rich user experience
  db.py     # SQLite schema, tags, FTS5, and queries
  ai.py     # optional Gemini integration
tests/
```

## License

MIT. See [LICENSE](LICENSE).

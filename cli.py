"""The command-line interface for second-brain-cli."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .ai import AIConfigurationError, answer_question
from .db import DEFAULT_DB_PATH, BrainDB, Note


app = typer.Typer(
    name="brain",
    help="A tiny, local-first second brain for your terminal.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _db(path: Path | None) -> BrainDB:
    return BrainDB(path or DEFAULT_DB_PATH)


def _relative_time(when: datetime) -> str:
    seconds = max(0, int((datetime.now(timezone.utc) - when).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86_400}d ago"


def _note_table(notes: list[Note]) -> Table:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="bold", width=6)
    table.add_column("Note", ratio=1)
    table.add_column("Tags", style="green")
    table.add_column("Date", style="dim", no_wrap=True)
    for note in notes:
        table.add_row(
            f"#{note.id}",
            note.text,
            ", ".join(note.tags) or "—",
            _relative_time(note.created_at),
        )
    return table


@app.command()
def add(
    text: Annotated[str, typer.Argument(help="The thought or fact to save.")],
    tag: Annotated[list[str] | None, typer.Option("--tag", "-t", help="Attach a tag; repeat for more.")] = None,
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """Save a thought."""
    try:
        note = _db(db_path).add_note(text, tag or [])
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    console.print(f"[bold green]Saved note #{note.id}[/]")
    if note.tags:
        console.print(f"[dim]tags:[/] [green]{', '.join(note.tags)}[/]")


@app.command("list")
def list_notes(
    tag: Annotated[str | None, typer.Option("--tag", "-t", help="Only show notes with this tag.")] = None,
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """List saved notes."""
    notes = _db(db_path).list_notes(tag)
    if not notes:
        suffix = f" tagged '{tag}'" if tag else ""
        console.print(f"[dim]No notes{suffix} yet. Save one with `brain add`.[/]")
        return
    console.print(_note_table(notes))


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Words to find in saved notes.")],
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """Find notes with local full-text search."""
    notes = _db(db_path).search_notes(query)
    if not notes:
        console.print("[dim]No matching notes found.[/]")
        return
    console.print(f"[bold]Found {len(notes)} note{'s' if len(notes) != 1 else ''}[/]\n")
    console.print(_note_table(notes))


@app.command()
def show(
    note_id: Annotated[int, typer.Argument(help="The ID of the note to show.")],
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """Show one note in full."""
    note = _db(db_path).get_note(note_id)
    if not note:
        console.print(f"[red]Note #{note_id} was not found.[/]")
        raise typer.Exit(1)
    metadata = f"Created: {note.created_at.astimezone().strftime('%b %d, %Y at %I:%M %p')}\nTags: {', '.join(note.tags) or '—'}"
    console.print(Panel(note.text, title=f"Note #{note.id}", subtitle=metadata, border_style="cyan"))


@app.command("delete")
def delete_note(
    note_id: Annotated[int, typer.Argument(help="The ID of the note to delete.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Delete without confirmation.")] = False,
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """Delete a note."""
    database = _db(db_path)
    note = database.get_note(note_id)
    if not note:
        console.print(f"[red]Note #{note_id} was not found.[/]")
        raise typer.Exit(1)
    if not yes and not typer.confirm(f"Delete note #{note_id}?"):
        console.print("[dim]Nothing deleted.[/]")
        return
    database.delete_note(note_id)
    console.print(f"[bold green]Deleted note #{note_id}[/]")


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="A question about your saved notes.")],
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """Ask Gemini a question grounded only in matching notes."""
    notes = _db(db_path).search_notes(question, limit=6)
    try:
        answer = answer_question(question, notes)
    except AIConfigurationError as error:
        console.print(f"[yellow]{error}[/]")
        raise typer.Exit(1)
    console.print(Panel(answer, title="Answer", border_style="cyan"))
    if notes:
        console.print("[dim]Based on notes: " + ", ".join(f"#{note.id}" for note in notes) + "[/]")


@app.command()
def stats(
    db_path: Annotated[Path | None, typer.Option("--db", hidden=True)] = None,
) -> None:
    """Show a few useful facts about your brain."""
    data = _db(db_path).stats()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    table.add_row("Total notes", str(data.total_notes))
    table.add_row("Created this week", str(data.notes_this_week))
    table.add_row("Most-used tags", ", ".join(f"{name} ({count})" for name, count in data.most_used_tags) or "—")
    table.add_row("Oldest note", f"#{data.oldest_note.id} · {_relative_time(data.oldest_note.created_at)}" if data.oldest_note else "—")
    table.add_row("Newest note", f"#{data.newest_note.id} · {_relative_time(data.newest_note.created_at)}" if data.newest_note else "—")
    console.print(Panel(table, title="Your second brain", border_style="cyan"))


if __name__ == "__main__":
    app()

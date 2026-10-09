"""Search, portable CSV output, and atomic local session persistence."""

from dataclasses import asdict, fields
import csv
import io
import json
import os
from pathlib import Path
import tempfile

from .models import Book, ScanResult

COLUMNS = tuple(field.name for field in fields(Book))


def search_books(books: list[Book], query: str = "", genre: str = "All genres",
                 file_format: str = "All formats") -> list[Book]:
    words = query.casefold().split()
    found = []
    for book in books:
        if genre != "All genres" and book.genre != genre:
            continue
        if file_format != "All formats" and book.format != file_format:
            continue
        haystack = " ".join((book.title, book.author, book.genre, book.subjects, book.relative_path)).casefold()
        if all(word in haystack for word in words):
            found.append(book)
    return found


def _atomic_text(path: Path, contents: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, newline="",
                                         dir=path.parent, prefix=".index-", delete=False) as stream:
            name = stream.name
            stream.write(contents)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _safe_cell(value: object) -> object:
    # Metadata is untrusted. Stop spreadsheet apps interpreting it as a formula.
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@"))
                                    or value.startswith(("\t", "\r", "\n", "'"))):
        return "'" + value
    return value


def _original_cell(value: str) -> str:
    # Reverse only the prefixes produced by this application's exporter.
    if value.startswith("'") and _safe_cell(value[1:]) == value:
        return value[1:]
    return value


def export_csv(books: list[Book], destination: str | Path) -> Path:
    path = Path(destination).expanduser().resolve()
    if path.suffix.lower() != ".csv":
        raise ValueError("Choose an output filename ending in .csv.")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    for book in books:
        writer.writerow({key: _safe_cell(value) for key, value in asdict(book).items()})
    # UTF-8 with BOM makes Tamil and other Unicode text open correctly in Excel.
    _atomic_text(path, buffer.getvalue(), encoding="utf-8-sig")
    return path


def read_csv(source: str | Path) -> list[Book]:
    with Path(source).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
            raise ValueError("This CSV is not an index exported by Personal Library Indexer.")
        books = []
        for line, row in enumerate(reader, 2):
            try:
                data = {key: _original_cell(row[key]) for key in COLUMNS}
                data["pages"] = int(data["pages"]) if data["pages"] else None
                data["size_bytes"] = int(data["size_bytes"])
                books.append(Book(**data))
            except (TypeError, ValueError, AttributeError) as error:
                raise ValueError(f"Invalid CSV row at line {line}.") from error
    return books


def save_session(result: ScanResult, directory: Path) -> None:
    if result.cancelled:
        raise ValueError("A cancelled scan cannot replace the saved catalogue.")
    payload = {"schema_version": 1, "root": result.root,
               "books": [asdict(book) for book in result.books], "warnings": result.warnings}
    # Each file is replaced atomically; the JSON is the authoritative UI session.
    export_csv(result.books, directory / "library_index.csv")
    _atomic_text(directory / "session.json", json.dumps(payload, ensure_ascii=False, indent=2))


def load_session(directory: Path) -> ScanResult | None:
    path = directory / "session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["schema_version"] != 1 or not isinstance(data["root"], str):
            raise ValueError("Unsupported saved index version.")
        books = []
        for entry in data["books"]:
            book = Book(**entry)
            for field in COLUMNS:
                if field not in {"pages", "size_bytes"} and not isinstance(getattr(book, field), str):
                    raise ValueError("Invalid saved book metadata.")
            if not isinstance(book.size_bytes, int) or (book.pages is not None and not isinstance(book.pages, int)):
                raise ValueError("Invalid saved book numbers.")
            books.append(book)
        warnings = data.get("warnings", [])
        if not isinstance(warnings, list) or not all(isinstance(w, str) for w in warnings):
            raise ValueError("Invalid saved scan warnings.")
        return ScanResult(root=data["root"], books=books, warnings=warnings)
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("The saved index is damaged. Scan a folder to rebuild it.") from error


def book_path(root: str, book: Book) -> Path:
    base = Path(root).resolve()
    path = (base / book.relative_path).resolve()
    if not path.is_relative_to(base) or path.suffix.lower() not in {".pdf", ".epub"}:
        raise ValueError("Book path is outside the indexed folder or has an unsupported format.")
    if not path.is_file():
        raise FileNotFoundError("The book has moved or was deleted. Scan its folder again.")
    return path

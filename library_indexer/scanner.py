"""Folder discovery and fault-tolerant indexing. No GUI dependencies."""

from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Event
from typing import Callable

from .extractors import extract_epub, extract_pdf, filename_title, LockedBookError
from .genres import classify_genre
from .models import Book, ScanResult

SUPPORTED = {".pdf", ".epub"}
MAX_FILE_BYTES = 100 * 1024 * 1024
Progress = Callable[[int, int, str], None]


def scan_folder(folder: str | Path, recursive: bool = True,
                progress: Progress | None = None, cancel: Event | None = None) -> ScanResult:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Folder does not exist: {root}")
    cancel = cancel if cancel is not None else Event()
    result = ScanResult(root=str(root))
    candidates: list[Path] = []

    def walk_error(error: OSError) -> None:
        result.warnings.append(f"Could not read a folder: {error.filename or error.strerror}")

    if progress:
        progress(0, 0, "Finding PDF and EPUB files...")
    for directory, dirs, names in os.walk(root, onerror=walk_error, followlinks=False):
        if cancel.is_set():
            result.cancelled = True
            return result
        # Skip symlink directories so a selected folder cannot escape its tree.
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink()) if recursive else []
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix.lower() in SUPPORTED and not path.is_symlink():
                candidates.append(path)
    candidates.sort(key=lambda p: p.relative_to(root).as_posix().casefold())
    for index, path in enumerate(candidates, 1):
        if cancel.is_set():
            result.cancelled = True
            break
        relative = path.relative_to(root).as_posix()
        if progress:
            progress(index - 1, len(candidates), relative)
        book = Book(title=filename_title(path), format=path.suffix[1:].upper(), relative_path=relative)
        try:
            stat = path.stat()
            book.size_bytes = stat.st_size
            book.modified_utc = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds")
            if stat.st_size > MAX_FILE_BYTES:
                raise ValueError("File exceeds the 100 MiB indexing limit.")
            extracted = extract_pdf(path) if book.format == "PDF" else extract_epub(path)
            book.title = extracted.title or book.title
            book.author = extracted.author or "Unknown"
            book.pages = extracted.pages
            book.language = extracted.language
            book.subjects = extracted.subjects
            book.genre, book.genre_basis = classify_genre(book.title, book.subjects, extracted.text)
            notes = list(extracted.notes)
            if not extracted.title:
                notes.append("Title metadata missing; filename used.")
            if not extracted.author:
                notes.append("Author metadata missing.")
            if book.genre == "Other":
                notes.append("Genre needs review.")
            book.notes = " ".join(notes)
            if notes:
                book.status = "warning"
        except LockedBookError as error:
            book.status = "encrypted"
            book.notes = str(error)
        except Exception as error:
            # A damaged e-book should not prevent the rest of a folder being indexed.
            book.status = "error"
            book.notes = f"Could not read file ({type(error).__name__}): {str(error)[:240]}"
        result.books.append(book)
        if progress:
            progress(index, len(candidates), relative)
    if cancel.is_set():
        result.cancelled = True
    return result

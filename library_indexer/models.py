"""Plain data objects shared by the scanner, desktop UI, and CLI."""

from dataclasses import dataclass, field


@dataclass
class Book:
    title: str
    author: str = "Unknown"
    genre: str = "Other"
    format: str = ""
    pages: int | None = None
    language: str = ""
    subjects: str = ""
    relative_path: str = ""
    size_bytes: int = 0
    modified_utc: str = ""
    status: str = "ok"
    notes: str = ""
    genre_basis: str = ""


@dataclass
class ScanResult:
    root: str
    books: list[Book] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cancelled: bool = False

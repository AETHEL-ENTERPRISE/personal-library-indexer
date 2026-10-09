"""Terminal interface, useful for evaluation on computers without a GUI."""

import argparse
from pathlib import Path
import sys

from library_indexer.catalog import export_csv, read_csv, search_books
from library_indexer.scanner import scan_folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index a folder of PDF and EPUB books into a searchable CSV.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Scan a folder and write a CSV index.")
    scan.add_argument("folder", type=Path)
    scan.add_argument("--output", "-o", type=Path, default=Path("data/library_index.csv"))
    scan.add_argument("--no-recursive", action="store_true", help="Only read files directly inside this folder.")
    search = subparsers.add_parser("search", help="Search an exported CSV index.")
    search.add_argument("csv_file", type=Path)
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--genre", default="All genres")
    search.add_argument("--format", choices=("PDF", "EPUB"), default="All formats", dest="file_format")
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            try:
                import pypdf  # noqa: F401
            except ImportError:
                print("Install dependencies: python -m pip install -r requirements.txt", file=sys.stderr)
                return 2
            result = scan_folder(args.folder, recursive=not args.no_recursive)
            output = export_csv(result.books, args.output)
            issues = sum(book.status != "ok" for book in result.books)
            print(f"Indexed {len(result.books)} books. {issues} need review.")
            print(f"CSV saved to: {output}")
            for warning in result.warnings:
                print(f"Warning: {warning}", file=sys.stderr)
            for book in result.books:
                if book.status != "ok":
                    print(f"[{book.status}] {book.relative_path}: {book.notes}")
            return 0
        books = search_books(read_csv(args.csv_file), args.query, args.genre, args.file_format)
        print(f"{len(books)} matching books")
        for book in books:
            print(f"{book.title} | {book.author} | {book.genre} | {book.format} | {book.relative_path}")
        return 0
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped. No partial CSV was written.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

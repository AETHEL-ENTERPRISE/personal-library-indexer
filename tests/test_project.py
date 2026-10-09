"""Behaviour tests using real PDFs/EPUBs and temporary folders."""

from dataclasses import replace
from pathlib import Path
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

from pypdf import PdfWriter

from library_indexer.catalog import book_path, export_csv, load_session, read_csv, save_session, search_books
from library_indexer.extractors import extract_epub
from library_indexer.genres import classify_genre
from library_indexer.models import Book, ScanResult
from library_indexer.scanner import scan_folder

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_books"


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_demo_books_have_expected_metadata(self):
        result = scan_folder(SAMPLES)
        self.assertEqual(len(result.books), 6)
        expected = {
            "Python for Curious Minds": "Technology", "An Introduction to Space": "Science",
            "Small Business Basics": "Business", "The Clockmaker's Secret": "Fiction",
            "Cities Through Time": "History", "Better Study Habits": "Self-help",
        }
        self.assertEqual({book.title: book.genre for book in result.books}, expected)
        self.assertTrue(all(book.author == "Demo Library" for book in result.books))
        self.assertTrue(all(book.status == "ok" for book in result.books))
        self.assertEqual(sum(book.format == "PDF" for book in result.books), 3)
        self.assertTrue(all(book.pages is None for book in result.books if book.format == "EPUB"))
        self.assertTrue(all(book.pages >= 1 for book in result.books if book.format == "PDF"))

    def test_nonrecursive_scan_excludes_nested_book(self):
        result = scan_folder(SAMPLES, recursive=False)
        self.assertEqual(len(result.books), 5)
        self.assertNotIn("Small Business Basics", [book.title for book in result.books])

    def test_uppercase_extension_and_unrelated_file(self):
        shutil.copyfile(SAMPLES / "Python_for_Curious_Minds.pdf", self.folder / "BOOK.PDF")
        (self.folder / "notes.txt").write_text("not an e-book")
        self.assertEqual([b.title for b in scan_folder(self.folder).books], ["Python for Curious Minds"])

    def test_empty_folder_is_a_valid_empty_index(self):
        self.assertEqual(scan_folder(self.folder).books, [])

    def test_missing_folder_has_useful_error(self):
        with self.assertRaisesRegex(ValueError, "Folder does not exist"):
            scan_folder(self.folder / "missing")

    def test_bad_books_do_not_interrupt_good_books(self):
        (self.folder / "bad.pdf").write_bytes(b"not a PDF")
        (self.folder / "bad.epub").write_bytes(b"not a ZIP")
        shutil.copyfile(SAMPLES / "The_Clockmakers_Secret.epub", self.folder / "good.epub")
        result = scan_folder(self.folder)
        self.assertEqual(len(result.books), 3)
        self.assertEqual(sorted(b.status for b in result.books), ["error", "error", "ok"])

    def test_encrypted_pdf_is_reported(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("demo-password")
        writer.write(self.folder / "locked.pdf")
        book = scan_folder(self.folder).books[0]
        self.assertEqual(book.status, "encrypted")
        self.assertIn("Encrypted PDF", book.notes)

    def test_missing_metadata_uses_filename_and_explains_ocr_limit(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(self.folder / "My_Reading-Notes.pdf")
        book = scan_folder(self.folder).books[0]
        self.assertEqual(book.title, "My Reading Notes")
        self.assertEqual(book.author, "Unknown")
        self.assertEqual(book.status, "warning")
        self.assertIn("OCR is not included", book.notes)

    def test_large_files_are_reported_before_parsing(self):
        shutil.copyfile(SAMPLES / "Python_for_Curious_Minds.pdf", self.folder / "book.pdf")
        with patch("library_indexer.scanner.MAX_FILE_BYTES", 10):
            result = scan_folder(self.folder)
        self.assertEqual(result.books[0].status, "error")
        self.assertIn("limit", result.books[0].notes)

    def test_cancel_before_scan(self):
        event = threading.Event()
        event.set()
        result = scan_folder(SAMPLES, cancel=event)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.books, [])

    def test_cancel_during_scan_preserves_saved_index(self):
        event = threading.Event()
        original = ScanResult(root=str(self.folder), books=[Book(title="Keep me")])
        save_session(original, self.folder / "data")

        def on_progress(done, total, name):
            if done == 1:
                event.set()

        partial = scan_folder(SAMPLES, progress=on_progress, cancel=event)
        self.assertTrue(partial.cancelled)
        self.assertEqual(len(partial.books), 1)
        with self.assertRaises(ValueError):
            save_session(partial, self.folder / "data")
        self.assertEqual(load_session(self.folder / "data").books[0].title, "Keep me")

    def test_search_is_case_insensitive_and_combines_filters(self):
        books = scan_folder(SAMPLES).books
        self.assertEqual(len(search_books(books, "PYTHON demo", "Technology", "PDF")), 1)
        self.assertEqual(len(search_books(books, "python", "History")), 0)
        self.assertEqual(len(search_books(books, "", file_format="EPUB")), 3)
        self.assertEqual(len(search_books(books, "reference/")), 1)

    def test_genre_rules_use_metadata_first_and_explain_matches(self):
        genre, evidence = classify_genre("A novel approach", "Computer programming", "history ancient empire")
        self.assertEqual(genre, "Technology")
        self.assertIn("Subjects", evidence)

    def test_genre_rules_do_not_match_substrings_or_nonfiction(self):
        self.assertEqual(classify_genre("A party", "Non-fiction", "")[0], "Other")
        self.assertEqual(classify_genre("", "", "A science lesson")[0], "Other")
        self.assertEqual(classify_genre("", "", "Python programming example")[0], "Technology")

    def test_mixed_genre_signals_are_not_guessed(self):
        self.assertEqual(classify_genre("", "History; Science", "")[0], "Other")

    def test_csv_roundtrip_unicode_commas_quotes_and_newlines(self):
        book = Book(title='தமிழ், "Stories"\nVolume 1', author="Zoë", genre="Fiction", format="EPUB", relative_path="books/தமிழ்.epub")
        target = export_csv([book], self.folder / "index.csv")
        self.assertEqual(read_csv(target), [book])
        self.assertTrue(target.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_csv_formula_cells_are_escaped_and_recoverable(self):
        titles = ["=1+1", " +CMD", "-2+3", "@SUM(A1)", "\tvalue", "'hello"]
        books = [Book(title=title) for title in titles]
        target = export_csv(books, self.folder / "safe.csv")
        with target.open(encoding="utf-8-sig", newline="") as stream:
            exported = list(csv.DictReader(stream))
        self.assertTrue(all(row["title"].startswith("'") for row in exported))
        self.assertEqual(read_csv(target), books)

    def test_output_must_be_csv(self):
        with self.assertRaisesRegex(ValueError, ".csv"):
            export_csv([], self.folder / "book.pdf")

    def test_invalid_csv_header_is_rejected(self):
        target = self.folder / "bad.csv"
        target.write_text("name,age\nExample,20\n")
        with self.assertRaisesRegex(ValueError, "not an index"):
            read_csv(target)

    def test_session_roundtrip_and_reload_of_manual_edit(self):
        original = scan_folder(SAMPLES)
        original.books[0] = replace(original.books[0], title="Reviewed title", genre="Arts")
        save_session(original, self.folder)
        loaded = load_session(self.folder)
        self.assertEqual(loaded, original)
        self.assertEqual(read_csv(self.folder / "library_index.csv"), original.books)

    def test_damaged_session_is_rejected(self):
        (self.folder / "session.json").write_text('{"schema_version":1}')
        with self.assertRaises(ValueError):
            load_session(self.folder)

    def test_path_traversal_and_unsupported_open_are_rejected(self):
        with self.assertRaises(ValueError):
            book_path(str(self.folder), Book(title="Bad", relative_path="../outside.pdf"))
        with self.assertRaises(ValueError):
            book_path(str(self.folder), Book(title="Bad", relative_path="program.exe"))

    def test_original_book_path_can_be_resolved(self):
        book = scan_folder(SAMPLES).books[0]
        self.assertTrue(book_path(str(SAMPLES), book).is_file())

    def test_symlink_files_are_not_followed(self):
        link = self.folder / "linked.pdf"
        try:
            link.symlink_to(SAMPLES / "Python_for_Curious_Minds.pdf")
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks requires privileges on some Windows systems.")
        self.assertEqual(scan_folder(self.folder).books, [])

    def test_epub_external_package_reference_is_rejected(self):
        path = self.folder / "external.epub"
        container = '''<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>
          <rootfile full-path="https://example.invalid/book.opf"/></rootfiles></container>'''
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("META-INF/container.xml", container)
        with self.assertRaisesRegex(ValueError, "External"):
            extract_epub(path)

    def test_epub_xml_entities_are_rejected(self):
        path = self.folder / "entities.epub"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("META-INF/container.xml", '<!DOCTYPE x [<!ENTITY a "a">]><x>&a;</x>')
        with self.assertRaisesRegex(ValueError, "declarations"):
            extract_epub(path)

    def test_cli_end_to_end_scan_and_search(self):
        target = self.folder / "cli.csv"
        scanned = subprocess.run([sys.executable, str(ROOT / "cli.py"), "scan", str(SAMPLES), "--output", str(target)],
                                 capture_output=True, text=True)
        self.assertEqual(scanned.returncode, 0, scanned.stderr)
        self.assertIn("Indexed 6 books", scanned.stdout)
        found = subprocess.run([sys.executable, str(ROOT / "cli.py"), "search", str(target), "python"],
                               capture_output=True, text=True)
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("1 matching books", found.stdout)
        self.assertIn("Python for Curious Minds", found.stdout)

    def test_cli_bad_folder_exits_nonzero(self):
        result = subprocess.run([sys.executable, str(ROOT / "cli.py"), "scan", str(self.folder / "missing")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Folder does not exist", result.stderr)


if __name__ == "__main__":
    unittest.main()

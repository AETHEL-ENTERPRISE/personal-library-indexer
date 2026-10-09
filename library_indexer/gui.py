"""Tkinter desktop interface. File parsing runs in a background thread."""

from dataclasses import replace
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import __version__
from .catalog import book_path, export_csv, load_session, save_session, search_books
from .genres import GENRES
from .models import Book, ScanResult
from .scanner import scan_folder

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BG = "#F2F5F8"
INK = "#172B3A"
MUTED = "#586E7E"
ACCENT = "#087F78"


class LibraryApp(tk.Tk):
    def __init__(self, data_dir: Path | None = None) -> None:
        super().__init__()
        self.title("Personal Library Indexer")
        width = min(1180, max(1000, self.winfo_screenwidth() - 80))
        height = min(880, max(700, self.winfo_screenheight() - 80))
        self.geometry(f"{width}x{height}")
        self.minsize(1000, 700)
        self.configure(bg=BG)
        self.data_dir = data_dir or PROJECT_ROOT / "data"
        self.catalogue = ScanResult(root="")
        self.visible: list[Book] = []
        self.busy = False
        self.cancel_event = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.sort_column = "title"
        self.sort_reverse = False
        self.folder = tk.StringVar()
        self.query = tk.StringVar()
        self.genre = tk.StringVar(value="All genres")
        self.file_format = tk.StringVar(value="All formats")
        self.recursive = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Choose a folder, or try the included sample books.")
        self.count_label = tk.StringVar(value="0 books")
        families = {name.casefold(): name for name in tkfont.families(self)}
        self.font_family = next((families[name] for name in
                                 ("segoe ui", "dejavu sans", "liberation sans", "helvetica", "arial")
                                 if name in families), tkfont.nametofont("TkDefaultFont").actual("family"))
        self._styles()
        self._build()
        self.query.trace_add("write", lambda *_: self.refresh())
        self.genre.trace_add("write", lambda *_: self.refresh())
        self.file_format.trace_add("write", lambda *_: self.refresh())
        self.bind("<Control-f>", self._focus_search)
        self.bind("<Control-o>", lambda _: self.browse())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_job = self.after(80, self._poll)
        try:
            previous = load_session(self.data_dir)
            if previous:
                self.catalogue = previous
                self.folder.set(previous.root)
                self.status.set("Saved index loaded. Scan again to include changed or new books.")
        except (OSError, ValueError) as error:
            self.status.set(f"Saved index could not be loaded: {error}")
        self._genre_options()
        self.refresh()

    def _styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=(self.font_family, 10), foreground=INK)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background=BG)
        style.configure("Card.TLabel", background="white")
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", padding=(13, 7), background="white", borderwidth=1)
        style.configure("Small.TButton", padding=(10, 3))
        style.map("TButton", background=[("active", "#E4EEEF"), ("disabled", "#EDF0F3")])
        style.configure("Accent.TButton", background=ACCENT, foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("disabled", "#93AAA8"), ("active", "#056861")],
                  foreground=[("disabled", "#F4F7F7")])
        style.configure("TEntry", padding=6, fieldbackground="white")
        style.configure("TCombobox", padding=7)
        style.configure("TCheckbutton", background=BG)
        style.configure("Treeview", rowheight=43, borderwidth=0, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", padding=(10, 12), background="#E8EEF3", font=(self.font_family, 10, "bold"))
        style.map("Treeview", background=[("selected", "#D6EFEB")], foreground=[("selected", INK)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#E0E8ED", borderwidth=0)

    def _build(self) -> None:
        header = tk.Frame(self, bg=INK, padx=26, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="PL /  PERSONAL LIBRARY", bg=INK, fg="#86DAD0",
                 font=(self.font_family, 10, "bold")).pack(anchor="w")
        tk.Label(header, text="Your books, easy to find.", bg=INK, fg="white",
                 font=(self.font_family, 22, "bold")).pack(anchor="w", pady=(3, 2))
        tk.Label(header, text="A searchable local catalogue for your PDF and EPUB collection.",
                 bg=INK, fg="#BED0DC", font=(self.font_family, 11)).pack(anchor="w")

        main = ttk.Frame(self, padding=(22, 12, 22, 10))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        source = ttk.Frame(main)
        source.grid(row=0, column=0, sticky="ew")
        source.columnconfigure(0, weight=1)
        ttk.Label(source, text="BOOK FOLDER", font=(self.font_family, 9, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.folder_entry = ttk.Entry(source, textvariable=self.folder)
        self.folder_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.browse_button = ttk.Button(source, text="Browse...", command=self.browse)
        self.browse_button.grid(row=1, column=1, padx=(0, 8))
        self.scan_button = ttk.Button(source, text="Scan folder", style="Accent.TButton", command=self.start_scan)
        self.scan_button.grid(row=1, column=2, padx=(0, 8))
        self.demo_button = ttk.Button(source, text="Try sample books", command=self.load_demo)
        self.demo_button.grid(row=1, column=3)
        self.recursive_check = ttk.Checkbutton(source, text="Include subfolders", variable=self.recursive)
        self.recursive_check.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.cancel_button = ttk.Button(source, text="Cancel scan", style="Small.TButton", command=self.cancel_scan, state="disabled")
        self.cancel_button.grid(row=2, column=2, columnspan=2, sticky="e", pady=(4, 0))

        stats = ttk.Frame(main)
        stats.grid(row=1, column=0, sticky="ew", pady=(10, 12))
        self.stat_values = []
        for i, label in enumerate(("BOOKS INDEXED", "PDF FILES", "EPUB FILES", "NEED REVIEW")):
            stats.columnconfigure(i, weight=1, uniform="stats")
            card = ttk.Frame(stats, style="Card.TFrame", padding=(17, 8))
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 3 else 5))
            value = tk.StringVar(value="0")
            self.stat_values.append(value)
            ttk.Label(card, textvariable=value, style="Card.TLabel", foreground=ACCENT,
                      font=(self.font_family, 20, "bold")).pack(anchor="w")
            ttk.Label(card, text=label, style="Card.TLabel", foreground=MUTED,
                      font=(self.font_family, 8, "bold")).pack(anchor="w")

        filters = ttk.Frame(main)
        filters.grid(row=2, column=0, sticky="ew")
        filters.columnconfigure(0, weight=1)
        ttk.Label(filters, text="Search title, author, subject or filename", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(filters, text="Genre", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=9)
        ttk.Label(filters, text="Format", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.search_entry = ttk.Entry(filters, textvariable=self.query)
        self.search_entry.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.genre_combo = ttk.Combobox(filters, textvariable=self.genre, values=("All genres",), state="readonly", width=16)
        self.genre_combo.grid(row=1, column=1, padx=9, pady=(5, 0))
        ttk.Combobox(filters, textvariable=self.file_format, values=("All formats", "PDF", "EPUB"),
                     state="readonly", width=12).grid(row=1, column=2, pady=(5, 0))
        ttk.Button(filters, text="Reset", command=self.reset_filters).grid(row=1, column=3, padx=(9, 0), pady=(5, 0))

        toolbar = ttk.Frame(main)
        toolbar.grid(row=3, column=0, sticky="ew", pady=(10, 6))
        ttk.Label(toolbar, text="COLLECTION", font=(self.font_family, 10, "bold")).pack(side="left")
        ttk.Label(toolbar, textvariable=self.count_label, style="Muted.TLabel").pack(side="left", padx=13)
        self.export_button = ttk.Button(toolbar, text="Export visible CSV", command=self.export_visible)
        self.export_button.pack(side="right")
        self.edit_button = ttk.Button(toolbar, text="Edit details", command=self.edit_selected, state="disabled")
        self.edit_button.pack(side="right", padx=8)
        self.open_button = ttk.Button(toolbar, text="Open book", command=self.open_selected, state="disabled")
        self.open_button.pack(side="right")

        table_box = ttk.Frame(main, style="Card.TFrame")
        table_box.grid(row=4, column=0, sticky="nsew")
        table_box.rowconfigure(0, weight=1)
        table_box.columnconfigure(0, weight=1)
        columns = ("title", "author", "genre", "format", "pages", "status")
        self.table = ttk.Treeview(table_box, columns=columns, show="headings", selectmode="browse", height=5)
        sizes = {"title": 360, "author": 160, "genre": 140, "format": 75, "pages": 65, "status": 90}
        for key in columns:
            self.table.heading(key, text=key.title(), anchor="w", command=lambda col=key: self.sort_by(col))
            self.table.column(key, width=sizes[key], minwidth=55, stretch=key in {"title", "author", "genre"}, anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_box, orient="vertical", command=self.table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.tag_configure("odd", background="#F7FAFC")
        self.table.tag_configure("issue", foreground="#916113")
        self.table.bind("<<TreeviewSelect>>", self.show_selected)
        self.table.bind("<Double-1>", self._double_click)
        self.empty_label = tk.Label(table_box, text="Build your first book index\n\nChoose a folder above, or click Try sample books.",
                                    bg="white", fg=MUTED, font=(self.font_family, 12), justify="center")

        self.details = tk.Text(main, height=3, wrap="word", relief="flat", bg="#E7EEF3", fg=INK,
                               font=(self.font_family, 10), padx=12, pady=8, state="disabled", takefocus=False)
        self.details.grid(row=5, column=0, sticky="ew", pady=(8, 8))
        self.progress = ttk.Progressbar(main, mode="determinate", maximum=100)
        self.progress.grid(row=6, column=0, sticky="ew")
        footer = ttk.Frame(main)
        footer.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel", wraplength=840).grid(row=0, column=0, sticky="w")
        ttk.Label(footer, text=f"LOCAL  /  v{__version__}", foreground=ACCENT,
                  font=(self.font_family, 9, "bold")).grid(row=0, column=1, sticky="e", padx=(10, 0))

    def _focus_search(self, _event=None) -> str:
        self.search_entry.focus_set()
        return "break"

    def browse(self) -> None:
        if self.busy:
            return
        selected = filedialog.askdirectory(title="Select your e-book folder", parent=self)
        if selected:
            self.folder.set(selected)

    def load_demo(self) -> None:
        if not self.busy:
            self.folder.set(str(PROJECT_ROOT / "sample_books"))
            self.recursive.set(True)
            self.start_scan()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for widget in (self.browse_button, self.scan_button, self.demo_button, self.folder_entry, self.recursive_check):
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        self.show_selected()

    def start_scan(self) -> None:
        if self.busy:
            return
        folder = self.folder.get().strip()
        if not folder:
            messagebox.showinfo("Choose a folder", "Click Browse and select a folder containing PDF or EPUB files.", parent=self)
            return
        if not Path(folder).expanduser().is_dir():
            messagebox.showerror("Folder not found", "Select an existing folder before scanning.", parent=self)
            return
        self.cancel_event = threading.Event()
        self._set_busy(True)
        self.progress["value"] = 0
        self.status.set("Finding PDF and EPUB files...")
        recursive = self.recursive.get()

        def work() -> None:
            try:
                result = scan_folder(folder, recursive=recursive, cancel=self.cancel_event,
                                     progress=lambda done, total, name: self.events.put(("progress", done, total, name)))
                self.events.put(("done", result))
            except Exception as error:
                self.events.put(("error", str(error)))

        threading.Thread(target=work, name="book-scanner", daemon=True).start()

    def cancel_scan(self) -> None:
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status.set("Cancelling after the current file. Your previous index will be kept.")

    def _poll(self) -> None:
        # Limit work per tick so a large queue cannot starve the UI event loop.
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "progress":
                _, done, total, name = event
                self.progress["value"] = 100 * done / total if total else 0
                if not self.cancel_event.is_set():
                    self.status.set(f"Scanning {done}/{total}: {name}" if total else name)
            elif kind == "done":
                self._set_busy(False)
                result = event[1]
                if result.cancelled:
                    self.progress["value"] = 0
                    self.status.set("Scan cancelled. Your previous index is unchanged.")
                    continue
                self.catalogue = result
                self.folder.set(result.root)
                self._genre_options()
                self.reset_filters()
                self.progress["value"] = 100
                self._save()
                if result.warnings:
                    messagebox.showwarning("Some folders were skipped", "\n".join(result.warnings[:8]), parent=self)
            elif kind == "error":
                self._set_busy(False)
                self.status.set("Scan failed. Your previous index is unchanged.")
                messagebox.showerror("Could not scan", event[1], parent=self)
        self.poll_job = self.after(80, self._poll)

    def _save(self) -> bool:
        try:
            save_session(self.catalogue, self.data_dir)
            count = len(self.catalogue.books)
            issues = sum(book.status != "ok" for book in self.catalogue.books)
            self.status.set(f"{count} books indexed | {issues} need review | Saved to data/library_index.csv")
            return True
        except (OSError, ValueError) as error:
            self.status.set("Index available in memory; automatic saving failed. Use Export visible CSV.")
            messagebox.showerror("Could not save index", str(error), parent=self)
            return False

    def _genre_options(self) -> None:
        values = ("All genres",) + tuple(sorted({book.genre for book in self.catalogue.books}))
        self.genre_combo.configure(values=values)
        if self.genre.get() not in values:
            self.genre.set("All genres")

    def reset_filters(self) -> None:
        self.query.set("")
        self.genre.set("All genres")
        self.file_format.set("All formats")
        self.refresh()

    def sort_by(self, column: str) -> None:
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else False
        self.sort_column = column
        self.refresh()

    def refresh(self) -> None:
        self.visible = search_books(self.catalogue.books, self.query.get(), self.genre.get(), self.file_format.get())
        column = self.sort_column
        self.visible.sort(key=lambda book: (book.pages if book.pages is not None else -1)
                          if column == "pages" else str(getattr(book, column)).casefold(), reverse=self.sort_reverse)
        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for i, book in enumerate(self.visible):
            label = {"ok": "Ready", "warning": "Review", "encrypted": "Locked", "error": "Unreadable"}.get(book.status, book.status)
            tags = (["odd"] if i % 2 else []) + (["issue"] if book.status != "ok" else [])
            self.table.insert("", "end", iid=str(i), values=(book.title, book.author, book.genre,
                              book.format, book.pages if book.pages is not None else "-", label), tags=tags)
        total = len(self.catalogue.books)
        numbers = (total, sum(b.format == "PDF" for b in self.catalogue.books),
                   sum(b.format == "EPUB" for b in self.catalogue.books), sum(b.status != "ok" for b in self.catalogue.books))
        for var, number in zip(self.stat_values, numbers):
            var.set(str(number))
        self.count_label.set(f"{len(self.visible)} of {total} books")
        if self.visible:
            self.empty_label.place_forget()
        else:
            message = "No matching books\n\nTry another search or reset the filters." if total else "Build your first book index\n\nChoose a folder above, or click Try sample books."
            self.empty_label.configure(text=message)
            self.empty_label.place(relx=0.5, rely=0.58, anchor="center")
        self.export_button.configure(state="normal" if self.visible else "disabled")
        self.show_selected()

    def selected_book(self) -> Book | None:
        selected = self.table.selection()
        if not selected:
            return None
        index = int(selected[0])
        return self.visible[index] if index < len(self.visible) else None

    def show_selected(self, _event=None) -> None:
        book = self.selected_book()
        self.open_button.configure(state="normal" if book else "disabled")
        self.edit_button.configure(state="normal" if book and not self.busy else "disabled")
        if book:
            text = f"{book.relative_path}  |  {book.size_bytes / 1024:,.1f} KB  |  Language: {book.language or 'not provided'}\n"
            text += f"Genre evidence: {book.genre_basis or 'unavailable'}\n"
            text += book.notes or "Ready. Double-click the row to open the original book."
        else:
            text = "Select a book to view its file path, genre evidence and any reading issues.\nGenre suggestions use simple keyword rules. You can correct the title, author or genre with Edit details."
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def _double_click(self, event) -> None:
        if self.table.identify_region(event.x, event.y) in {"cell", "tree"}:
            self.open_selected()

    def open_selected(self) -> None:
        book = self.selected_book()
        if not book:
            return
        try:
            path = book_path(self.catalogue.root, book)
            if sys.platform == "win32":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not open book", str(error), parent=self)

    def export_visible(self) -> None:
        if not self.visible:
            return
        filename = filedialog.asksaveasfilename(parent=self, title="Export current results", defaultextension=".csv",
                                              initialfile="library_index.csv", filetypes=[("CSV index", "*.csv")])
        if not filename:
            return
        try:
            path = export_csv(self.visible, filename)
            self.status.set(f"Exported {len(self.visible)} books to {path.name}")
            messagebox.showinfo("Export complete", f"Saved {len(self.visible)} books to:\n{path}", parent=self)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not export", str(error), parent=self)

    def edit_selected(self) -> None:
        book = self.selected_book()
        if not book or self.busy:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Edit catalogue details")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        box = ttk.Frame(dialog, padding=24)
        box.pack(fill="both", expand=True)
        variables = {name: tk.StringVar(value=getattr(book, name)) for name in ("title", "author", "genre")}
        for index, (name, variable) in enumerate(variables.items()):
            ttk.Label(box, text=name.title()).grid(row=index * 2, column=0, sticky="w", pady=(8, 3))
            if name == "genre":
                field = ttk.Combobox(box, textvariable=variable, values=GENRES, state="readonly", width=45)
            else:
                field = ttk.Entry(box, textvariable=variable, width=48)
            field.grid(row=index * 2 + 1, column=0, sticky="ew")
        ttk.Label(box, text="Changes update this index. Source e-books stay unchanged.\nA new scan rebuilds metadata and replaces these edits.",
                  style="Muted.TLabel").grid(row=6, column=0, sticky="w", pady=14)

        def apply() -> None:
            title = variables["title"].get().strip()
            if not title:
                messagebox.showerror("Title required", "Enter a book title.", parent=dialog)
                return
            updated = replace(book, title=title[:2000], author=variables["author"].get().strip()[:2000] or "Unknown",
                              genre=variables["genre"].get(), genre_basis="Manually reviewed in the catalogue.")
            # Extraction warnings remain visible; editing metadata does not fix an unreadable file.
            index = next(i for i, item in enumerate(self.catalogue.books) if item is book)
            self.catalogue.books[index] = updated
            self._save()
            self._genre_options()
            self.refresh()
            dialog.destroy()

        buttons = ttk.Frame(box)
        buttons.grid(row=7, column=0, sticky="e")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=8)
        ttk.Button(buttons, text="Save details", style="Accent.TButton", command=apply).pack(side="left")
        dialog.grab_set()
        dialog.focus_set()

    def close(self) -> None:
        self.cancel_event.set()
        self.after_cancel(self.poll_job)
        self.destroy()


def main() -> None:
    app = LibraryApp()
    app.mainloop()

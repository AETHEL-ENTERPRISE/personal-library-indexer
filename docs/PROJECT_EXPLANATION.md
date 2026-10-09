# Personal Library Indexer: project explanation

## Simple introduction

Personal Library Indexer helps a user organise e-books stored on their computer. It scans a selected folder for PDF and EPUB files, reads details such as title and author, suggests a genre, and saves the information in a CSV file. The user can search and filter the catalogue using a desktop interface.

## Problem and objective

A folder with many e-books is difficult to search when filenames are unclear. Opening every book wastes time. This project creates one local catalogue so the user can find books without opening each file individually.

The main objective is to convert an unorganised folder into a useful list of book titles, authors, genres and file locations.

## Technologies used

| Technology | Why it is used |
| --- | --- |
| Python | Main programming language |
| Tkinter / ttk | Desktop interface supplied with standard desktop Python distributions |
| pypdf | PDF metadata, page count and selectable text |
| zipfile | Read EPUB containers without extracting files to disk |
| ElementTree | Read EPUB XML metadata |
| HTMLParser | Read text from EPUB chapters |
| pathlib / os | Find files and manage paths |
| csv / json | Export the catalogue and save local application state |
| threading / queue | Scan files without blocking the interface event loop |
| unittest | Check important behaviours automatically |

## How one scan works

1. The user selects a folder and starts the scan.
2. The scanner finds `.pdf` and `.epub` files. It can include subfolders.
3. The correct reader extracts metadata and a small text sample from each book.
4. If the title is missing, the filename is cleaned and used as a fallback.
5. Keyword rules suggest a genre and record the reason for the suggestion.
6. A `Book` data object holds the extracted information.
7. The interface shows the results and lets the user search or filter them.
8. The complete index is saved as CSV. A JSON session stores the original folder and metadata so the app can reload them.

Search checks whether every word in the query appears in a book's searchable fields. It ignores differences between uppercase and lowercase letters. Genre and file-format filters are applied along with the search.

## Why there are several modules

The user interface, file scanning, book readers, genre rules and storage are separate responsibilities. Keeping them in separate files makes the code easier to explain and maintain. The desktop app and CLI reuse the same scanning and search functions.

The worker thread reads files. It sends progress and results into a queue. The Tkinter event loop checks that queue and updates widgets on the main thread. This avoids calling GUI widgets from the worker thread.

## Error handling

- A damaged book becomes an error row; other books continue to be processed.
- An encrypted PDF becomes a locked row.
- Missing title or author metadata uses a fallback and adds a warning.
- A missing folder is reported before scanning.
- A cancelled scan keeps the previous saved catalogue.
- A failed save is shown to the user; the in-memory results can still be exported elsewhere.

Each completed output file is written to a temporary file before replacing the old file. This reduces the chance of leaving a half-written index. The CSV and JSON are each replaced separately; they are not a multi-file database transaction.

## Complexity

Let `F` be the number of filesystem entries visited, `N` the number of supported books, and `R` the total parsing work for those books.

- Discovery is approximately **O(F)**; sorting the candidate paths takes **O(N log N)**.
- Scanning and extraction take approximately **O(F + N log N + R)**. Parsing cost depends on the size and internal structure of each PDF or EPUB.
- With `Q` query words and at most `L` searchable characters per record, a linear search is approximately **O(N × Q × L)** using straightforward substring checks.
- Sorting displayed results takes **O(N log N)**.
- The catalogue and file list use **O(N)** record/path storage, plus the active reader's memory and sampled text. Parsing libraries may use additional memory beyond the sample size.

## Small demonstration

Say: "I will scan the six sample e-books. The program reads PDF and EPUB metadata, classifies the books using keyword rules, and creates a CSV catalogue. When I search for Python, only the relevant book is shown. I can also filter EPUB files and export those results. The original e-books are not changed."

Then demonstrate the exact steps in the README's evaluation section.

## Common viva questions

**1. What is metadata?**  
Metadata is information about a file, such as its title, author, subject and language.

**2. What is an EPUB file?**  
EPUB is an e-book format whose container uses ZIP. Inside it are metadata, chapter files and other resources. This project reads the metadata and a few chapters directly from that container.

**3. Why use CSV?**  
CSV is simple, portable and easy to open in spreadsheets. A small personal catalogue does not require a database server.

**4. Is the genre classifier an AI model?**  
No. It uses fixed English keyword rules. It checks subjects first, then the title, then sampled text. The evidence is visible to the user.

**5. Why can genre detection be wrong?**  
A keyword can have several meanings, metadata can be incomplete, and a small sample may not describe the whole book. Unclear results are labelled Other, and users can edit the genre.

**6. Why does the interface use a thread?**  
Reading many files takes time. A background thread keeps the main interface responsive while the files are scanned.

**7. Why are EPUB page counts blank?**  
EPUB text usually reflows depending on the reader, font size and screen. It does not have one reliable fixed page count like a PDF.

**8. Does it search every sentence in every book?**  
No. Search uses the catalogue fields: title, author, genre, subjects and relative file path. The sampled body text is used only for genre classification.

**9. What happens if metadata is missing?**  
The filename becomes the title, the author becomes Unknown, and a warning is shown.

**10. Does it change the original books?**  
No. It reads them and writes separate catalogue files. Editing details changes only the catalogue.

**11. What testing was done?**  
The automated suite exercises actual sample PDFs and EPUBs, damaged and encrypted files, searching, CSV output, saved-session reload, cancellation and CLI behaviour. Run it yourself with the command in the README.

**12. What could be added later?**  
OCR for scanned pages, persistent corrections across rescans, more language rules, duplicate detection and a database for larger collections are possible extensions. They are not implemented in this version.

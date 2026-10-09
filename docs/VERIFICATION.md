# Verification notes

Verified on 9 October 2026 with Python 3.12.14, pypdf 6.20.0 and Linux. The desktop checks used Tk 9.0 on a virtual display.

## Core behaviour

All **28 automated tests passed** using:

```bash
python -m unittest discover -s tests -v
```

The suite checks actual PDF/EPUB extraction, nested-folder scanning, missing metadata, corrupt and encrypted books, cancellation, genre rules, filtering, Unicode CSV round trips, formula escaping, local persistence, file path checks and CLI execution.

The six sample books produced **six records with zero review warnings**, including three PDF records and three EPUB records. Each suggested genre matched the sample collection table.

## Desktop checks

The real Tkinter interface was launched and exercised. These checks passed:

- Initial empty state and sample-book button.
- Background scanning, disabled controls during a scan, and completed counters.
- Live case-insensitive search and the empty-results state.
- Genre and format filters.
- Exporting three visible EPUB books while retaining all six in the full saved index.
- Sorting, selection and genre evidence in the detail panel.
- Edit dialog saving a changed title.
- Restarting the application and reloading that edited title.
- Rescanning to rebuild metadata from the original books.
- Window layouts at 1180 x 880 and 1000 x 700.

Open-book dispatch was checked by capturing the requested operating-system command and verifying that its target file existed. An external PDF/EPUB viewer was not launched during this automated check.

The sample PDF pages were rendered and visually checked. The screenshot in the README is from the actual running desktop application.

## Platform scope

The Windows batch launcher and GitHub Actions workflow are included, but were not executed on Windows or on GitHub in this preparation environment. The workflow is configured to run core tests on Windows and Ubuntu after upload. Test the Windows launcher once on your laptop before submitting your repository link.

The checks use the included sample collection and temporary test files. They do not establish perfect extraction or correct genre classification for every possible e-book.

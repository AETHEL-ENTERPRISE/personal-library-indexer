"""Rebuild original demo documents. Optional dependency: pip install reportlab."""

from pathlib import Path
from xml.sax.saxutils import escape
import zipfile

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1] / "sample_books"
AUTHOR = "Demo Library"
FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("DemoSans", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("DemoSansBold", str(FONT_DIR / "VeraBd.ttf")))

PDF_BOOKS = [
    ("Python_for_Curious_Minds.pdf", "Python for Curious Minds", "Technology; Programming", [
        ("Small programs, useful results", "A computer program is a set of instructions. Python lets us express those instructions in a readable way. Start with a small problem: count files, rename photographs, or organise a reading list."),
        ("Store, repeat, decide", "Variables store values. Loops repeat an action. Conditions choose which action to take. Combining these ideas creates useful software without needing a large program."),
        ("Build a tiny catalogue", "Read filenames from a folder, collect the title of each book, and write the results to a CSV file. A list holds the records while a dictionary gives each record named fields. Test the program with an empty folder as well as a full one."),
    ]),
    ("An_Introduction_to_Space.pdf", "An Introduction to Space", "Science; Astronomy", [
        ("Our moving neighbourhood", "The solar system contains the Sun, planets, moons, and many smaller objects. Gravity influences their motion. Astronomy uses observation and physical models to understand these objects."),
        ("Looking carefully", "A telescope collects light. Scientists compare observations over time, looking for patterns and testing explanations. A useful observation includes both a measurement and an estimate of its uncertainty."),
        ("Questions lead to science", "Why do some planets have rings? How do stars change? A good science question can be investigated with evidence. Curiosity becomes knowledge when an explanation survives careful testing."),
    ]),
    ("reference/Small_Business_Basics.pdf", "Small Business Basics", "Business; Entrepreneurship", [
        ("Begin with a real problem", "A business helps a customer solve a problem. Before building a product, speak to possible customers and understand what they already do. A small experiment can reveal more than a long list of assumptions."),
        ("Know the numbers", "Revenue is money earned from sales. Costs are the resources spent to deliver the product. Tracking both helps a founder understand whether the business can continue. Keep clear records rather than relying on memory."),
        ("Improve one step at a time", "Marketing explains the value of a product to the right customer. Feedback reveals where it disappoints. A simple cycle of making, measuring, and improving is easier to manage than trying every idea at once."),
    ]),
]

EPUB_BOOKS = [
    ("The_Clockmakers_Secret.epub", "The Clockmaker's Secret", "Fiction; Mystery", [
        "At closing time, Mira heard a clock strike thirteen. The sound came from a cabinet that had been locked for years. Beside the cabinet lay a brass key and a note in her grandfather's handwriting.",
        "The note contained only one instruction: listen before you look. Mira waited. Between the ticks she heard a soft click from the floor. A loose tile lifted to reveal a letter, not a treasure map.",
        "Her grandfather had repaired the town's clocks for forty years. The letter named every neighbour who had helped him when his workshop flooded. His secret was a record of kindness. Mira put a fresh page beside it and wound the clock.",
    ]),
    ("Cities_Through_Time.epub", "Cities Through Time", "History; Civilizations", [
        "Studying history means asking how people lived and how their choices changed a place. Ancient cities grew around water, trade, and shared work. Their buildings offer clues, but buildings alone cannot tell the whole story.",
        "Archaeology compares physical evidence with written records. A broken pot, a road, or a market plan can help explain ordinary life. Historians must also ask whose experiences were left out of surviving records.",
        "Cities continue to change. Comparing maps from different periods helps reveal new transport routes and disappearing neighbourhoods. A careful account separates evidence from an attractive guess.",
    ]),
    ("Better_Study_Habits.epub", "Better Study Habits", "Self-help; Productivity", [
        "A useful habit starts small. Choose one clear task for a short study session and remove one distraction. A timetable is easier to follow when it leaves room for meals, rest, and unexpected work.",
        "After reading a topic, close the book and explain the main idea in your own words. Check what you missed and try again later. This creates a practical feedback loop for learning.",
        "Personal development does not require a perfect day. Keep a simple record of what you practised, adjust unrealistic goals, and return to the routine after an interruption. Consistency grows through manageable decisions.",
    ]),
]


def make_pdf(relative: str, title: str, subjects: str, sections: list[tuple[str, str]]) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A5, rightMargin=34, leftMargin=34,
                            topMargin=38, bottomMargin=38, title=title, author=AUTHOR,
                            subject=subjects, pageCompression=1)
    small = ParagraphStyle("small", fontName="DemoSans", fontSize=8, leading=11, textColor=colors.HexColor("#587080"))
    heading = ParagraphStyle("heading", fontName="DemoSansBold", fontSize=22, leading=27,
                              textColor=colors.HexColor("#172B3A"), spaceAfter=15)
    section = ParagraphStyle("section", fontName="DemoSansBold", fontSize=11, leading=15,
                              textColor=colors.HexColor("#087F78"), spaceBefore=14, spaceAfter=5)
    body = ParagraphStyle("body", fontName="DemoSans", fontSize=9, leading=14, alignment=TA_LEFT)
    story = [Paragraph("PERSONAL LIBRARY INDEXER / DEMO COLLECTION", small), Spacer(1, 19),
             Paragraph(escape(title), heading), Paragraph(f"{AUTHOR} | {escape(subjects)}", small), Spacer(1, 4)]
    for name, text in sections:
        story.extend([Paragraph(escape(name), section), Paragraph(escape(text), body)])
    story.extend([Spacer(1, 20), Paragraph("Original short sample for software testing. Included under the project's MIT license.", small)])
    doc.build(story)


def make_epub(filename: str, title: str, subjects: str, paragraphs: list[str]) -> None:
    path = ROOT / filename
    title_xml = escape(title)
    subject_xml = "".join(f"<dc:subject>{escape(s.strip())}</dc:subject>" for s in subjects.split(";"))
    package = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:pli:demo:{escape(path.stem)}</dc:identifier>
    <dc:title>{title_xml}</dc:title><dc:creator>{AUTHOR}</dc:creator>
    <dc:language>en</dc:language>{subject_xml}
    <dc:rights>MIT License; original demo content.</dc:rights>
    <meta property="dcterms:modified">2026-10-09T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine><itemref idref="chapter"/></spine>
</package>'''
    chapter = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head><title>{title_xml}</title></head>
<body><h1>{title_xml}</h1><p>By {AUTHOR}</p>{''.join('<p>' + escape(p) + '</p>' for p in paragraphs)}
<p>Original short sample for Personal Library Indexer. MIT License.</p></body></html>'''
    navigation = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
<head><title>Contents</title></head><body><nav epub:type="toc" id="toc"><h1>Contents</h1>
<ol><li><a href="chapter.xhtml">{title_xml}</a></li></ol></nav></body></html>'''
    container = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("EPUB/package.opf", package)
        archive.writestr("EPUB/chapter.xhtml", chapter)
        archive.writestr("EPUB/nav.xhtml", navigation)


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for book in PDF_BOOKS:
        make_pdf(*book)
    for book in EPUB_BOOKS:
        make_epub(*book)
    print("Created six original sample e-books in sample_books/.")

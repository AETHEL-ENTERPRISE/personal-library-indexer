"""Read e-book metadata and a small text sample without changing source files."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

MAX_TEXT_CHARS = 24_000
MAX_XML_BYTES = 4 * 1024 * 1024
MAX_EPUB_ENTRIES = 10_000
NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class LockedBookError(ValueError):
    """A password or DRM prevents indexing the book."""


@dataclass
class Extracted:
    title: str = ""
    author: str = ""
    subjects: str = ""
    language: str = ""
    pages: int | None = None
    text: str = ""
    notes: list[str] = field(default_factory=list)


def clean(value: object, limit: int = 2000) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ")
    return " ".join(text.split())[:limit]


def filename_title(path: Path) -> str:
    return clean(re.sub(r"[_-]+", " ", path.stem)) or "Untitled"


def extract_pdf(path: Path) -> Extracted:
    from pypdf import PdfReader

    result = Extracted()
    # The context manager releases file handles, including on parsing errors.
    with path.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        if reader.is_encrypted:
            # Password-protected PDFs are reported, not password-cracked.
            raise LockedBookError("Encrypted PDF; use an unlocked copy you can access.")
        meta = reader.metadata or {}
        result.title = clean(meta.get("/Title"))
        if result.title.casefold() in {"untitled", "untitled document", "document"}:
            result.title = ""
        result.author = clean(meta.get("/Author"))
        result.subjects = clean(" ".join(clean(meta.get(k)) for k in ("/Subject", "/Keywords")))
        result.language = clean(reader.trailer["/Root"].get("/Lang", ""))
        result.pages = len(reader.pages)
        # Fill absent docinfo values from XMP where available.
        try:
            xmp = reader.xmp_metadata
            if xmp:
                titles = xmp.dc_title or {}
                result.title = result.title or clean(titles.get("x-default") or next(iter(titles.values()), ""))
                result.author = result.author or clean("; ".join(xmp.dc_creator or []))
                result.subjects = result.subjects or clean("; ".join(xmp.dc_subject or []))
                result.language = result.language or clean("; ".join(xmp.dc_language or []))
        except Exception:
            result.notes.append("XMP metadata could not be read.")
        pieces = []
        for index in range(min(result.pages, 5)):
            try:
                page = reader.pages[index]
                content = page.get_contents()
                if content is not None and len(content.get_data()) > 8 * 1024 * 1024:
                    result.notes.append(f"Page {index + 1} text skipped: complex content.")
                    continue
                pieces.append((page.extract_text() or "")[:MAX_TEXT_CHARS])
                if sum(map(len, pieces)) >= MAX_TEXT_CHARS:
                    break
            except Exception:
                result.notes.append(f"Text from page {index + 1} could not be read.")
        result.text = " ".join(pieces)[:MAX_TEXT_CHARS]
        if not result.text.strip():
            result.notes.append("No selectable text found in sampled pages; OCR is not included.")
    return result


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _member_name(base: str, href: str) -> str:
    """Resolve an EPUB reference inside its ZIP; never extract to disk."""
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        raise ValueError("External EPUB resources are not fetched.")
    relative = unquote(parts.path)
    if "\\" in relative or relative.startswith("/"):
        raise ValueError("Invalid EPUB member path.")
    name = posixpath.normpath(posixpath.join(base, relative))
    if name == ".." or name.startswith("../"):
        raise ValueError("EPUB path leaves its archive.")
    return name


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > MAX_XML_BYTES:
        raise ValueError("EPUB metadata or chapter exceeds the 4 MiB reading limit.")
    if info.flag_bits & 1:
        raise LockedBookError("Encrypted EPUB member cannot be read.")
    return archive.read(info)


def _xml(data: bytes) -> ET.Element:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Custom XML declarations are not supported.")
    return ET.fromstring(data)


def extract_epub(path: Path) -> Extracted:
    result = Extracted()
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > MAX_EPUB_ENTRIES:
            raise ValueError("EPUB contains too many archive entries.")
        container = _xml(_read_member(archive, "META-INF/container.xml"))
        roots = container.findall("container:rootfiles/container:rootfile", NS)
        rootfile = next((r for r in roots if r.get("media-type") == "application/oebps-package+xml"), None)
        if rootfile is None:
            rootfile = roots[0] if roots else None
        if rootfile is None or not rootfile.get("full-path"):
            raise ValueError("EPUB has no package document.")
        opf_path = _member_name("", rootfile.attrib["full-path"])
        package = _xml(_read_member(archive, opf_path))
        metadata = package.find("opf:metadata", NS)
        if metadata is None:
            raise ValueError("EPUB package has no metadata section.")

        def values(tag: str) -> list[str]:
            return [clean("".join(node.itertext())) for node in metadata.findall("dc:" + tag, NS)]

        result.title = next(iter(values("title")), "")
        result.author = "; ".join(values("creator"))
        result.subjects = "; ".join(values("subject"))
        result.language = "; ".join(values("language"))
        # Follow the reading order, not arbitrary ZIP file order.
        manifest = {node.get("id"): node for node in package.findall("opf:manifest/opf:item", NS)}
        chapters = []
        for itemref in package.findall("opf:spine/opf:itemref", NS):
            item = manifest.get(itemref.get("idref"))
            if item is not None and item.get("media-type") in {"application/xhtml+xml", "text/html"}:
                chapters.append(item.get("href", ""))
        pieces = []
        for href in chapters[:5]:
            try:
                name = _member_name(str(PurePosixPath(opf_path).parent), href)
                parser = _TextParser()
                parser.feed(_read_member(archive, name).decode("utf-8-sig", errors="replace"))
                pieces.append(" ".join(parser.parts)[:MAX_TEXT_CHARS])
                if sum(map(len, pieces)) >= MAX_TEXT_CHARS:
                    break
            except Exception:
                result.notes.append("A sampled EPUB chapter could not be read.")
        result.text = " ".join(pieces)[:MAX_TEXT_CHARS]
        if not result.text.strip():
            result.notes.append("No readable chapter text found; metadata only.")
    return result

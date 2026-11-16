#!/usr/bin/env python3
"""Check local links and preserve Yu Qi's original site byte for byte.

Run with Python 3 from any directory. No server or dependencies are needed.
The checksum manifest comes from upstream commit
8284ee6c8e892a5f2b8d86fabae2d71bda2b0e76, before the move to /yuqi/.
"""

import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    "index.html",
    "events/index.html",
    "team/index.html",
    "publications/index.html",
    "paper-reading/index.html",
    "opportunities/index.html",
    "yuqi/index.html",
)


def check_personal_site(errors):
    manifest = ROOT / "scripts/yuqi-original.sha256"
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"Cannot read personal-site checksum manifest: {exc}")
        return 0

    expected = {}
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            errors.append(f"Malformed checksum at manifest line {number}")
            continue
        digest, name = parts
        if (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
                or not name.startswith("yuqi/") or ".." in Path(name).parts
                or name in expected):
            errors.append(f"Invalid checksum entry at manifest line {number}")
            continue
        expected[name] = digest

    if len(expected) != 67:
        errors.append(f"Personal-site manifest must contain 67 files; found {len(expected)}")

    personal = ROOT / "yuqi"
    actual = set()
    if personal.is_symlink():
        errors.append("Protected personal-site directory must not be a symlink: yuqi/")
    if personal.is_dir():
        for path in personal.rglob("*"):
            name = path.relative_to(ROOT).as_posix()
            if path.is_symlink():
                errors.append(f"Personal-site file must not be a symlink: {name}")
            if path.is_file() or path.is_symlink():
                actual.add(name)

    for name in sorted(expected.keys() - actual):
        errors.append(f"Missing original personal-site file: {name}")
    for name in sorted(actual - expected.keys()):
        errors.append(f"Extra file in protected personal site: {name}")
    for name in sorted(expected.keys() & actual):
        try:
            digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"Cannot read personal-site file {name}: {exc}")
            continue
        if digest != expected[name]:
            errors.append(f"Original personal-site file has changed: {name}")
    return len(expected)


def local_target(value, source, context, errors):
    """Resolve a browser URL relative to its HTML file, within this site."""
    value = value.strip()
    if not value or value.startswith("#"):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        errors.append(f"{context}: invalid URL {value!r}: {exc}")
        return None
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    if path.startswith("/"):
        errors.append(f"{context}: use a directory-relative URL, not {value!r}")
        return None
    target = (source.parent / path).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        errors.append(f"{context}: URL leaves the site directory: {value!r}")
        return None
    return target


class LinkChecker(HTMLParser):
    def __init__(self, source, errors):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.errors = errors
        self.count = 0

    def handle_starttag(self, tag, attrs):
        context = f"{self.source.relative_to(ROOT).as_posix()}:{self.getpos()[0]}"
        if tag == "base":
            self.errors.append(f"{context}: base elements change directory-relative URL resolution")
        for name, value in attrs:
            if value is None or name not in {"href", "src", "poster"}:
                continue
            target = local_target(value, self.source, context, self.errors)
            if target is None:
                continue
            self.count += 1
            if target.is_dir() and name == "href":
                target = target / "index.html"
            if not target.is_file():
                self.errors.append(f"{context}: missing local {name} target {value!r}")

    handle_startendtag = handle_starttag


def check_html(errors):
    count = 0
    for name in PAGES:
        path = ROOT / name
        try:
            html = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"Cannot read required page {name}: {exc}")
            continue
        parser = LinkChecker(path, errors)
        parser.feed(html)
        parser.close()
        count += parser.count
    return count


def check_publications(errors):
    path = ROOT / "site-data/publications.json"
    try:
        publications = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot read publications data: {exc}")
        return 0
    if not isinstance(publications, list) or not publications:
        errors.append("Publications data must be a non-empty JSON array")
        return 0
    scholar_ids = {}
    for index, publication in enumerate(publications, 1):
        context = f"site-data/publications.json publication {index}"
        if not isinstance(publication, dict):
            errors.append(f"{context}: record must be a JSON object")
            continue
        title = publication.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{context}: title must be a non-empty string")
        for field in ("authors", "conference"):
            if not isinstance(publication.get(field), str):
                errors.append(f"{context}: {field} must be a string")
        if publication.get("type") not in {"journal", "conference", "preprint", "workshop"}:
            errors.append(f"{context}: type must be journal, conference, preprint, or workshop")
        year = publication.get("year")
        if ("year" not in publication or
                (year is not None and (type(year) is not int or not 1000 <= year <= 9999))):
            errors.append(f"{context}: year must be a four-digit integer or null")

        links = publication.get("links")
        if not isinstance(links, dict) or not links:
            errors.append(f"{context}: links must be a non-empty JSON object")
        else:
            for label, url in links.items():
                if not isinstance(label, str) or not isinstance(url, str):
                    errors.append(f"{context}: link labels and URLs must be strings")
                    continue
                try:
                    parsed = urlsplit(url)
                    valid = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
                except ValueError:
                    valid = False
                if not valid:
                    errors.append(f"{context}: link {label!r} must use an absolute HTTP(S) URL")

        if "scholar_id" in publication:
            scholar_id = publication["scholar_id"]
            if not isinstance(scholar_id, str) or not scholar_id.strip():
                errors.append(f"{context}: scholar_id must be a non-empty string")
            else:
                scholar_id = scholar_id.strip()
                if scholar_id in scholar_ids:
                    errors.append(f"{context}: duplicate scholar_id {scholar_id!r} "
                                  f"(also publication {scholar_ids[scholar_id]})")
                else:
                    scholar_ids[scholar_id] = index

        thumbnail = publication.get("thumbnail")
        if thumbnail is None:
            continue
        if not isinstance(thumbnail, str):
            errors.append(f"{context}: thumbnail must be a string when provided")
            continue
        if not thumbnail.strip():
            continue
        target = local_target(thumbnail, ROOT / "index.html", context, errors)
        if target is None:
            errors.append(f"{context}: thumbnail must be a local directory-relative path")
        elif not target.is_file():
            errors.append(f"{context}: missing thumbnail {thumbnail!r}")
    return len(publications)


def main():
    errors = []
    personal_count = check_personal_site(errors)
    link_count = check_html(errors)
    publication_count = check_publications(errors)
    if errors:
        print(f"Site check failed ({len(errors)} errors):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Site check passed: {personal_count} original personal files unchanged; "
          f"{len(PAGES)} HTML pages and {link_count} local links checked; "
          f"{publication_count} publication records checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import html
import re
import textwrap
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"
OUTPUTS = ROOT / "outputs"


@dataclass(frozen=True)
class SourcePage:
    title: str
    url: str
    filename: str


PAGES = [
    SourcePage(
        "Success Profiles",
        "https://www.gov.uk/government/publications/success-profiles",
        "01_success_profiles.html",
    ),
    SourcePage(
        "Success Profiles - Candidate Overview",
        "https://www.gov.uk/government/publications/success-profiles/success-profiles-candidate-overview",
        "02_candidate_overview.html",
    ),
    SourcePage(
        "A Brief Guide To Competencies",
        "https://www.gov.uk/guidance/a-brief-guide-to-competencies",
        "03_brief_guide_to_competencies.html",
    ),
    SourcePage(
        "Success Profiles - Experience",
        "https://www.gov.uk/government/publications/success-profiles/success-profiles-experience",
        "04_experience.html",
    ),
    SourcePage(
        "Success Profiles - Strengths",
        "https://www.gov.uk/government/publications/success-profiles/success-profiles-strengths",
        "05_strengths.html",
    ),
    SourcePage(
        "Success Profiles - Civil Service Behaviours",
        "https://www.gov.uk/government/publications/success-profiles/success-profiles-civil-service-behaviours",
        "06_civil_service_behaviours.html",
    ),
    SourcePage(
        "Success Profiles - Technical",
        "https://www.gov.uk/government/publications/success-profiles/success-profiles-technical",
        "07_technical.html",
    ),
    SourcePage(
        "Success Profiles - Ability",
        "https://www.gov.uk/government/publications/success-profiles/success-profiles-ability",
        "08_ability.html",
    ),
]


DOWNLOADS = [
    (
        "civil_service_competency_framework_2013_2017.pdf",
        "https://www.gov.uk/government/uploads/system/uploads/attachment_data/file/436073/cscf_fulla4potrait_2013-2017_v2d.pdf",
    )
]


class MarkdownContentParser(HTMLParser):
    """Convert a selected GOV.UK content fragment into readable markdown."""

    def __init__(self, base_url: str, heading_offset: int = 1) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.heading_offset = heading_offset
        self.lines: list[str] = []
        self.current: list[str] = []
        self.prefix = ""
        self.skip_depth = 0
        self.link_stack: list[str] = []
        self.table_cell_open = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)

        if tag in {"script", "style", "svg", "noscript", "button"}:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag in {"h1", "h2", "h3", "h4"}:
            self._finish()
            level = min(6, int(tag[1]) + self.heading_offset)
            self.prefix = "#" * level + " "
        elif tag == "p":
            self._finish()
            self.prefix = ""
        elif tag == "li":
            self._finish()
            self.prefix = "- "
        elif tag in {"dt", "dd"}:
            self._finish()
            self.prefix = ""
        elif tag == "br":
            self._finish()
        elif tag == "tr":
            self._finish()
        elif tag in {"th", "td"}:
            if self.table_cell_open:
                self.current.append(" | ")
            self.table_cell_open = True
        elif tag == "a":
            href = attr.get("href")
            self.link_stack.append(urllib.parse.urljoin(self.base_url, href or ""))

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            if tag in {"script", "style", "svg", "noscript", "button"}:
                self.skip_depth -= 1
            return

        if tag == "a" and self.link_stack:
            self.link_stack.pop()
        elif tag in {"h1", "h2", "h3", "h4", "p", "li", "dt", "dd", "tr"}:
            self._finish()
            if tag == "tr":
                self.table_cell_open = False
        elif tag in {"th", "td"}:
            self.table_cell_open = False

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return

        text = " ".join(html.unescape(data).replace("\xa0", " ").split())
        if not text:
            return

        if self.link_stack:
            href = self.link_stack[-1]
            if href and href != text:
                text = f"[{text}]({href})"

        if self.current and not self.current[-1].endswith((" ", "\n", "| ")):
            self.current.append(" ")
        self.current.append(text)

    def markdown(self) -> str:
        self._finish()
        text = "\n\n".join(line for line in self.lines if line.strip())
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _finish(self) -> None:
        if not self.current:
            self.prefix = ""
            return

        line = "".join(self.current).strip()
        self.current = []
        if not line:
            self.prefix = ""
            return

        self.lines.append(self.prefix + line)
        self.prefix = ""


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 source capture for personal application reference"
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 source capture for personal application reference"
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def extract_title(raw: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, flags=re.I | re.S)
    if not match:
        return ""
    return clean_inline_html(match.group(1))


def extract_updated(raw: str) -> str:
    match = re.search(r"Updated\s*</[^>]+>\s*<[^>]+>\s*([^<]+)", raw, flags=re.I | re.S)
    if match:
        return clean_inline_html(match.group(1)).rstrip(" -\u2014")
    match = re.search(r"Last updated\s*</[^>]+>\s*<[^>]+[^>]*>\s*([^<]+)", raw, flags=re.I | re.S)
    if match:
        return clean_inline_html(match.group(1)).rstrip(" -\u2014")
    return ""


def extract_govspeak_fragments(raw: str) -> list[str]:
    starts = [
        m.start()
        for m in re.finditer(
            r"<div[^>]+class=\"[^\"]*(?:gem-c-govspeak|govuk-govspeak|govspeak)[^\"]*\"",
            raw,
            flags=re.I,
        )
    ]

    fragments: list[str] = []
    for start in starts:
        fragment = extract_balanced_div(raw, start)
        if fragment and len(strip_tags(fragment)) > 200:
            # Avoid keeping nested duplicates when both wrapper and inner govspeak div match.
            if not any(fragment in existing for existing in fragments):
                fragments.append(fragment)

    # Prefer the largest content block. It normally contains the actual publication body.
    fragments.sort(key=len, reverse=True)
    return fragments[:1]


def extract_attachments(raw: str, base_url: str) -> list[tuple[str, str]]:
    attachments: list[tuple[str, str]] = []
    pattern = re.compile(
        r"<h3[^>]+class=\"[^\"]*gem-c-attachment__title[^\"]*\"[^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>",
        flags=re.I | re.S,
    )
    for href, text in pattern.findall(raw):
        label = clean_inline_html(text)
        url = urllib.parse.urljoin(base_url, href)
        if label and url:
            attachments.append((label, url))
    return attachments


def extract_balanced_div(raw: str, start: int) -> str:
    tag_pattern = re.compile(r"</?div\b[^>]*>", flags=re.I)
    depth = 0
    for match in tag_pattern.finditer(raw, start):
        token = match.group(0)
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return raw[start : match.end()]
        else:
            depth += 1
    return ""


def clean_inline_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text).replace("\xa0", " ")
    return " ".join(text.split())


def strip_tags(raw: str) -> str:
    return clean_inline_html(raw)


def fragment_to_markdown(fragment: str, base_url: str) -> str:
    parts: list[str] = []
    cursor = 0
    table_pattern = re.compile(r"<table\b.*?</table>", flags=re.I | re.S)

    matches = list(table_pattern.finditer(fragment))
    index = 0
    while index < len(matches):
        match = matches[index]

        before = fragment[cursor : match.start()]
        before_md = html_fragment_to_markdown(before, base_url)
        if before_md:
            parts.append(before_md)

        group = [match.group(0)]
        group_end = match.end()
        index += 1

        while index < len(matches):
            gap = fragment[group_end : matches[index].start()]
            if strip_tags(gap).strip():
                break
            group.append(matches[index].group(0))
            group_end = matches[index].end()
            index += 1

        table_md = tables_to_markdown(group)
        if table_md:
            parts.append(table_md)

        cursor = group_end

    tail = fragment[cursor:]
    tail_md = html_fragment_to_markdown(tail, base_url)
    if tail_md:
        parts.append(tail_md)

    text = "\n\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_fragment_to_markdown(fragment: str, base_url: str) -> str:
    parser = MarkdownContentParser(base_url, heading_offset=1)
    parser.feed(fragment)
    return parser.markdown()


def tables_to_markdown(tables: list[str]) -> str:
    header: list[str] | None = None
    rows: list[list[str]] = []

    for table in tables:
        parsed_rows = parse_table_rows(table)
        if not parsed_rows:
            continue

        first_is_header = table.lower().find("<th") != -1
        if first_is_header and header is None:
            header = parsed_rows[0]
            rows.extend(parsed_rows[1:])
        elif first_is_header:
            # If GOV.UK repeats the same header in consecutive tables, keep one header.
            if parsed_rows[0] == header:
                rows.extend(parsed_rows[1:])
            else:
                rows.extend(parsed_rows)
        else:
            rows.extend(parsed_rows)

    if not rows and not header:
        return ""

    width = len(header or rows[0])
    if header is None:
        header = [f"Column {i}" for i in range(1, width + 1)]

    normalized_rows = [normalize_table_row(row, width) for row in rows]
    normalized_header = normalize_table_row(header, width)

    lines = [
        "| " + " | ".join(escape_table_cell(cell) for cell in normalized_header) + " |",
        "| " + " | ".join("---" for _ in normalized_header) + " |",
    ]
    for row in normalized_rows:
        lines.append("| " + " | ".join(escape_table_cell(cell) for cell in row) + " |")

    return "\n".join(lines)


def parse_table_rows(table: str) -> list[list[str]]:
    row_pattern = re.compile(r"<tr\b.*?</tr>", flags=re.I | re.S)
    cell_pattern = re.compile(r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", flags=re.I | re.S)
    rows: list[list[str]] = []
    for row_html in row_pattern.findall(table):
        cells = [clean_inline_html(cell) for cell in cell_pattern.findall(row_html)]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    return rows


def normalize_table_row(row: list[str], width: int) -> list[str]:
    if len(row) < width:
        return row + [""] * (width - len(row))
    if len(row) > width:
        return row[: width - 1] + [" ".join(row[width - 1 :])]
    return row


def escape_table_cell(cell: str) -> str:
    return cell.replace("|", "\\|")


def normalise_ascii(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a3": "GBP ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("ascii", errors="ignore").decode("ascii")


def wrap_markdown(text: str) -> str:
    text = re.sub(r"(?m)(^- .+)\n\n(?=- )", r"\1\n", text)
    wrapped_lines = []
    for line in text.splitlines():
        if not line.strip():
            wrapped_lines.append("")
        elif line.startswith("#") or line.lstrip().startswith("- ") or line.startswith("|") or line.startswith("Source: ") or line.startswith("Downloaded: "):
            wrapped_lines.append(line)
        elif re.match(r"^\d+\.", line):
            wrapped_lines.append(line)
        elif len(line) > 120:
            wrapped_lines.append("\n".join(textwrap.wrap(line, width=110)))
        else:
            wrapped_lines.append(line)
    return "\n".join(wrapped_lines).strip() + "\n"


def insert_table_of_contents(capture: str) -> str:
    lines = capture.splitlines()
    toc: list[str] = ["## Table of Contents", ""]
    seen: dict[str, int] = {}

    for line in lines:
        if not line.startswith("##"):
            continue
        if line.startswith("######"):
            continue
        if line.strip() == "## Table of Contents":
            continue

        level = len(line) - len(line.lstrip("#"))
        if level > 4:
            continue

        title = line.lstrip("#").strip()
        anchor = markdown_anchor(title, seen)
        indent = "  " * (level - 2)
        toc.append(f"{indent}- [{title}](#{anchor})")

    toc.append("")

    insert_at = 0
    separator_count = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            separator_count += 1
            insert_at = i
            break

    if separator_count == 0:
        return capture

    new_lines = lines[:insert_at] + [""] + toc + lines[insert_at:]
    return "\n".join(new_lines) + "\n"


def markdown_anchor(title: str, seen: dict[str, int]) -> str:
    anchor = title.lower()
    anchor = re.sub(r"`([^`]+)`", r"\1", anchor)
    anchor = re.sub(r"[^a-z0-9 _-]", "", anchor)
    anchor = anchor.replace(" ", "-")
    anchor = re.sub(r"-+", "-", anchor).strip("-")

    count = seen.get(anchor, 0)
    seen[anchor] = count + 1
    if count:
        return f"{anchor}-{count}"
    return anchor


def build_capture() -> str:
    SOURCES.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    sections: list[str] = [
        "# Civil Service Success Profiles - GOV.UK Source Capture",
        "",
        "Generated from official GOV.UK pages. This file is a cleaned markdown capture of the visible source content, not an interpretation guide.",
        "",
        "Source start point: https://www.gov.uk/government/publications/success-profiles",
        "",
        "Reuse note: GOV.UK content is normally available under the Open Government Licence unless otherwise stated on the source page. Keep attribution and source links with this capture.",
        "",
    ]

    for index, page in enumerate(PAGES, start=1):
        print(f"Fetching {index}/{len(PAGES)}: {page.url}")
        raw = fetch(page.url)
        (SOURCES / page.filename).write_text(raw, encoding="utf-8")

        page_title = extract_title(raw) or page.title
        updated = extract_updated(raw)
        attachments = extract_attachments(raw, page.url)
        fragments = extract_govspeak_fragments(raw)

        sections.extend(["---", "", f"## {index}. {page_title}", "", f"Source: {page.url}", ""])
        if updated:
            sections.extend([f"Updated: {updated}", ""])

        if attachments:
            sections.extend(["### Documents", ""])
            for label, url in attachments:
                sections.append(f"- [{label}]({url})")
            sections.append("")

        if not fragments:
            sections.extend(["No GOV.UK body content block was extracted from this page.", ""])
            continue

        body = fragment_to_markdown(fragments[0], page.url)
        sections.extend([body, ""])

    for filename, url in DOWNLOADS:
        print(f"Downloading linked source: {url}")
        (SOURCES / filename).write_bytes(fetch_bytes(url))
        sections.extend(
            [
                "---",
                "",
                "## Linked Source File",
                "",
                f"Filename: {filename}",
                "",
                f"Source: {url}",
                "",
            ]
        )

    capture = "\n".join(sections).strip() + "\n"
    capture = normalise_ascii(capture)
    capture = insert_table_of_contents(capture)
    return wrap_markdown(capture)


def main() -> None:
    capture = build_capture()
    output = OUTPUTS / "success_profiles_govuk_source_capture.md"
    output.write_text(capture, encoding="utf-8")
    root_output = ROOT / "success_profiles_govuk_source_capture.md"
    root_output.write_text(capture, encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Wrote {root_output}")


if __name__ == "__main__":
    main()
